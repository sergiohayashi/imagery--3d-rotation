// src/components/ContextArtifact/SystemMessage.js
import React, {useState, useEffect, useContext, useRef} from 'react';
import MaxModal from '../MaxModal/MaxModal'
// import { getApi } from '../../services/apiService';
import {AppContext} from "../../redux/AppContext";
import styles from "./FileContextTop.module.css"
import {ThemeContext} from "../../redux/ThemeContext";
import { useNavigate  } from 'react-router-dom';
import SystemMessageEditor from "../SystemMessageEditor/SystemMessageEditor";
import {useApi} from "../../hooks/useApi";
import {FaPlus, FaTrash, FaTrashCan} from "react-icons/fa6";
import {FaAngleLeft, FaCheck, FaEdit, FaPlusCircle} from "react-icons/fa";
import {Title} from "../Headings/Heading";
import {TbFileSpark} from "react-icons/tb";
import Busy from "../Busy/Busy";
import {uploadDocumentsUsingS3_forFileContext} from "./FileUploaderForContext";
import {uploadDocumentsUsingS3} from "../Chat/FileUploader";
import {
    setCurrentChatId,
    setCurrentFileContext,
    setCurrentFileContextLength, setErrorMessage,
    setInfoMessage
} from "../../redux/actions";
import {GoTriangleDown} from "react-icons/go";
import ContextModal from "../ContextModal/ContextModal";
import DragAndDrop from "../DragAndDrop/DragAndDrop";
import {AiOutlineLoading3Quarters} from "react-icons/ai";

const MAX_FILES = 50;

const MAX_FILE_SIZE_MB = 10;                 // 10 MB
const MAX_FILE_SIZE = MAX_FILE_SIZE_MB * 1024 * 1024;
const isFileTooLarge = (file) => file.size > MAX_FILE_SIZE;


function FileContextTop() {
    const { state, dispatch } = useContext(AppContext);
    const { projectList, currentProject, showNav, isMobile, currentFileContext, currentFileContextLength } = state;
    const [filesList, setFilesList] = useState([]);
    const api = useApi();
    const [loading, setLoading] = useState(false);
    const fileInputRefNew = useRef(null);
    const [refreshUntil, setRefreshUntil] = useState(null);
    const intervalId = useRef(null);
    const [showFileContextSwitch, setShowFileContextSwitch]= useState(null);
    const [fileContextTitle, setFileContextTitle] = useState(null);
    const [fileContextList, setFileContextList] = useState([]);
    const [showNewFileContextModal, setNewFileContextModal] = useState(null);
    const [showEditContextModal, setEditContextModal] = useState(null);
    const filesListRef = useRef([]);

    useEffect(() => {
        filesListRef.current = filesList;
    }, [filesList]);

    const loadList = async () => {
        if (currentFileContext?.id) {
            const result = await api.get(`/api/file_context/${currentFileContext?.id}/files`)
            setFilesList(result.data);

        } else {
            setFilesList([]);
        }
    }

    useEffect(() => {
        if (currentProject) {
            loadFileContextList();
        }
    }, [currentProject]);


    useEffect(()=> {
        loadList();
    }, [currentFileContext])

    useEffect(()=> {
        dispatch(setCurrentFileContextLength((filesList || []).length));
    }, [filesList]);


    useEffect(()=> {
        if (!currentFileContext?.id) return;
        if (!refreshUntil) return;
        if (Date.now()> refreshUntil) return;  // stop refresh
        const fetch_ = async () => {
            const result = await api.get(`/api/file_context/${currentFileContext?.id}/files`)
            setFilesList(result.data);
        }
        fetch_();

        // continue refresh
        intervalId.current = setInterval(()=> {
            if (Date.now() > refreshUntil) {
                const hasProcessing = filesListRef.current.some(
                    (obj) => obj.status === "processing"
                );
                if (!hasProcessing) {
                    console.log('Expired refresh time. Finish refresh. hasProcessing=', hasProcessing,
                        'filesList', filesListRef.current
                    );
                    clearInterval(intervalId.current);
                    intervalId.current = null;
                    return;
                } else {
                    console.log('Expired refresh time, but continue while has file in processing');
                }
            }

            // reload
            fetch_();
        }, 2000);

        return () => clearInterval(intervalId.current);
    }, [refreshUntil]);


    const loadFileContextList = async () => {
        try {
            const result = await api.get('/api/file_context', {
                params: {
                    project_id: currentProject.id,
                }
            })
            const newList = [{
                id: null,
                title: "(clear selection)"
            }, ...result.data]
            setFileContextList(newList);
            return newList;
        } catch (error) {
            console.log( 'Error: ', error);
        }
        return []
    }

    const handleFileChangeNewForFileContext = async (event) => {
        const file = event.target.files[0];
        if (!file) {
            console.log( 'No file selected!', file);
            return;
        }

        await handleDropFilesNewForFileContext(event.target.files);
        event.target.value = "";
    };


    const handleDropFilesNewForFileContext = async (dropFiles) => {
        console.log( 'dropFilesNew', dropFiles);
        const files = Array.from(dropFiles);

        const validFiles = [];
        files.forEach((file) => {
            if (isFileTooLarge(file)) {
                dispatch(setErrorMessage(`"${file.name}" is larger than ${MAX_FILE_SIZE_MB} MB and was skipped.`));
            } else {
                validFiles.push(file);
            }
        });

        if (validFiles.length === 0) return;
        // if (dropFiles.length<= 0) return;

        const numberOfFilesToLoad = Math.min(validFiles.length, MAX_FILES-currentFileContextLength);
        if (numberOfFilesToLoad<= 0) {
            dispatch(setInfoMessage(`Maximum number of files exceeded`));
            return;

        }
        if (numberOfFilesToLoad < validFiles.length)
        {
            dispatch(setInfoMessage(`Maximum number of files exceeded. Only files within the limit will be uploaded.${numberOfFilesToLoad}/${dropFiles.length}`))
        }
        try {
            setLoading(true);
            for (let i = 0; i < numberOfFilesToLoad; i++) {
                await handleFileInputNewForFileContext(validFiles[i]);
            }
            await loadList();
            setRefreshUntil( Date.now() + 20_000);
            // moveScrollToEnd();
        } catch (error) {
            console.error('Error uploading file:', error);
        } finally {
            setLoading(false);
        }
    };


    const handleFileInputNewForFileContext = async (file) => {
        if (isFileTooLarge(file)) {
            dispatch(setErrorMessage(`"${file.name}" is larger than ${MAX_FILE_SIZE_MB} MB and was skipped.`));
            return;
        }

        await uploadDocumentsUsingS3_forFileContext(api, file, currentProject.id, currentFileContext.id);
        // await loadList();
        // setMessages(current =>  [...current, {
        //     role: "user",
        //     content: null,
        //     // preset_id:  response.data.file_url,
        //     file_url: response.file_url,
        //     file_name: file.name,
        //     content_type: response.content_type,
        //     entry_id: null,
        // }]);
    }

    const onDidPaste = async (event) => {
        try {
            setLoading(true);

            // Use event.clipboardData directly
            const clipboardItems = event.clipboardData?.items || event.originalEvent?.clipboardData?.items;

            if (!clipboardItems) {
                console.warn("No clipboard data found.");
                return;
            }
            let imagePasted = false;
            let files = []
            for (let item of clipboardItems) {
                // if (item.kind === "file" && item.type.startsWith("image/")) {
                if (item.kind === "file") {
                    files.push(item.getAsFile());
                    // const file = item.getAsFile();
                    // await handleFileInputNew(file);
                    imagePasted = true;
                }
            }

            if (currentFileContextLength + files.length> MAX_FILES) {
                files = files.slice(0,MAX_FILES-currentFileContextLength);
            }
            for (let f of files) {
                await handleFileInputNewForFileContext(f);
            }

            // Prevent Monaco Editor from inserting "image.png" or similar text
            if (imagePasted) {
                console.log("Stop propagation");
                event.preventDefault();  // Stop default paste behavior
                event.stopPropagation(); // Stop Monaco from handling it further
                // moveScrollToEnd();
            }
        } catch (error) {
            console.error('Error uploading file:', error);
        } finally {
            setLoading(false);
        }
    }

    const handleDeleteFile = async (id) => {
        try {
            setLoading(true);
            await api.delete(`/api/file_context/${currentFileContext.id}/files/${id}`);
            await loadList();
        } finally {
            setLoading(false);
        }
    }

    const handleCreateNewFileContext = async () => {
        try {
            setLoading(true);
            await api.post(`/api/file_context`,
                {
                    title: fileContextTitle,
                    project_id: currentProject.id
                }
            );
            const newList = await loadFileContextList();

            // switch to new context
            // setTimeout(()=> {
            if (newList.length>1) {   // first position is empty
                console.log('contextList ', newList);
                dispatch(setCurrentFileContext(newList[1]))
            }
            // }, 1000);
        } finally {
            setLoading(false);
        }
    }

    const handleEditFileContext = async () => {
        try {
            setLoading(true);
            await api.put(`/api/file_context/${currentFileContext.id}`,
                {
                    title: fileContextTitle,
                    project_id: currentProject.id
                }
            );
            const newList = await loadFileContextList();
            dispatch(setCurrentFileContext(newList.find(item=>item.id === currentFileContext.id)));
        } finally {
            setLoading(false);
        }
    }

    const filesListDiv = <div className={styles['files-list']}>
        {(filesList || []).map((f, index) => <div className={`${styles["files-row"]} list-item`}>
            <div>{index+1}</div>
            <div className={styles['files-name-col']}>
                <div className={styles['files-name']}>
                    <a href={f?.file_url} target="_blank" rel="noopener noreferrer" className={styles["file-link"]}>
                        {f?.file_name}
                    </a>
                    {f.status === "processing" && <>
                        <div className={"fa-icon loading-anim"}>
                            <AiOutlineLoading3Quarters/>
                        </div>
                    </>}
                </div>
                {f.status === "error" && <div className={styles['file-error']}>
                    {f.error}
                </div>}
            </div>
            <div className={styles['files-controls']}>
                <div className={"fa-icon -smaller -delete"}
                    onClick={()=>handleDeleteFile(f.id)}
                    title = "Delete this file"
                >
                    <FaTrash/>
                </div>
            </div>
        </div>)}
    </div>


    const handleDeleteCurrentFileContext = async () => {
        if (!window.confirm("Delete current context and all the files?")) return;

        try {
            setLoading(true);
            await api.delete(`/api/file_context/${currentFileContext.id}`);
            await loadFileContextList();
            dispatch(setCurrentFileContext(null));
        } catch (error) {
            console.error(error);
        } finally {
            setLoading(false);
        }
    }

    const triggerFileInputNewForFileContext = () => {
        fileInputRefNew.current.click();
    };

    const newFileContextModal = !!showNewFileContextModal && (
        <ContextModal
            show={!!showNewFileContextModal}
            clickPosition = {showNewFileContextModal}
            handleClose={() => {
                setNewFileContextModal( false);
            }}
        >
            <div className={`${styles["modal-container"]} context-modal-margin`}>
                <input
                    type={"text"}
                    className={"input"}
                    autoFocus
                    value={fileContextTitle}
                    onChange = {e=>setFileContextTitle(e.target.value)}/>
                <button
                    className={"button"}
                    onClick = {async () => {
                        await handleCreateNewFileContext();
                        setNewFileContextModal(null);
                    }}
                >Save</button>
            </div>
        </ContextModal>
    )

    const editContextModal = !!showEditContextModal && (
        <ContextModal
            show={!!showEditContextModal}
            clickPosition = {showEditContextModal}
            handleClose={() => {
                setEditContextModal( false);
            }}
        >
            <div className={`${styles["modal-container"]} context-modal-margin`}>
                <input
                    type={"text"}
                    className={"input"}
                    autoFocus
                    value={fileContextTitle}
                    onChange = {e=>setFileContextTitle(e.target.value)}/>
                <button
                    className={"button"}
                    onClick = {async () => {
                        await handleEditFileContext();
                        setEditContextModal(false);
                    }}
                >Update</button>
            </div>
        </ContextModal>
    )


    const fileContextSwitchModal = !!showFileContextSwitch && (
        <ContextModal
            clickPosition ={showFileContextSwitch}
            handleClose={() => setShowFileContextSwitch(null)} closeLabel={"Close"}>
            <div className={styles["modal-list-container-scroll"]}>
                {(fileContextList || []).map((d, index) => (
                    <div className={"selection-list-item"} key={index} onClick={() => {
                        dispatch(setCurrentFileContext(d));
                        // dispatch(setCurrentChatId(null));
                        setShowFileContextSwitch(null);

                        // navigate('/file-context');
                    }}>
                        {currentFileContext?.id === d.id ? <>
                            <div className={`${styles["file-context-row"]} ${styles["-selected"]}`}>
                                <div className={styles['modal-list-title']}>{d.title} </div>
                                <div className={styles['file-count']}>{d.file_count >0? `${d.file_count} files`:''}</div>
                                <div className={"accept"}>
                                    <FaCheck/>
                                </div>
                            </div>
                            </>:<>
                            <div className={styles["file-context-row"]}>
                                <div className={styles['modal-list-title']}>{d.title} </div>
                                <div className={styles['file-count']}>{d.file_count >0? `${d.file_count} files`:''}</div>
                            </div>
                        </>}

                    </div>
                ))}
            </div>
        </ContextModal>
    )

    const contextSwitchDiv = (<div>
        <div className={styles['tab-nav-file-context-parent']}>
            {/*<div className={"bold"}>Select file context: </div>*/}
            <div className={styles["tab-nav-file-context"]} onClick={async (e) => {
                const rect = e.target.getBoundingClientRect();
                await loadFileContextList();
                setShowFileContextSwitch({top: rect.top, left: rect.left});
            }}>
                {currentFileContext?.id?  currentFileContext.title: 'select...'}
                <GoTriangleDown size={19}/>
            </div>
        </div>
    </div>)


    return <div className={styles['container']}>
        {/*<DragAndDrop onFileDrop={handleDropFilesNewForFileContext}/>*/}
        <div className={styles["control-panel"]}>
            <Title>File Context</Title>
            <div className={styles['obs']}>
                <div className={"bold"}>Restrictions:</div>
                <ul>
                    <li>{`Max file size: ${MAX_FILE_SIZE_MB}MB`}</li>
                    <li>{`Maximum number of files per context: ${MAX_FILES}`}</li>
                    <li>Max chunks or page per file: 173 (others will be ignored for chunk extraction)</li>
                    <li>Max 3 images per page of pdf file</li>
                    <li>Allowed file formats: text files in general, images and pdf.</li>
                </ul>
            </div>
            <div className={styles["combo-and-button"]}>
                {contextSwitchDiv}
                <div className={styles["context-panel"]}>
                    <button className={`icon-button-with-text button ${!!currentFileContext?'':'display-none'} delete`}
                            onClick={()=>handleDeleteCurrentFileContext()}
                            title="Delete this context"
                    >
                        {/*<div>Delete Context</div>*/}
                        <FaTrashCan />
                    </button>
                    <button className={`icon-button-with-text button ${!!currentFileContext?'':'display-none'}`}
                            onClick={(e) => {
                                const rect = e.target.getBoundingClientRect();
                                setFileContextTitle(currentFileContext.title);
                                setEditContextModal({top:rect.top, left:rect.left});
                            }}
                            title="Edit name"
                    >
                        {/*<div>New Context</div>*/}
                        <FaEdit/>
                    </button>
                    <button className={"icon-button-with-text button"}
                         onClick={(e) => {
                             const rect = e.target.getBoundingClientRect();
                             setNewFileContextModal({top:rect.top, left:rect.left});
                         }}
                        title="Create new context"
                    >
                        {/*<div>New Context</div>*/}
                        <FaPlusCircle/>
                    </button>
                </div>
            </div>
            {/*<textarea*/}
            {/*    style={{width: "100%", border: "none", padding: "8px" }}*/}
            {/*    value={"copy past files here..."}*/}
            {/*    onPaste ={onDidPaste}*/}
            {/*/>*/}
            <div className={`${styles["file-context-control"]} ${!!currentFileContext?'':'display-none'}`}>
                <div className={styles['context-panel']}>
                    {/*<button className={`icon-button-with-text button`}*/}
                    {/*        onClick={triggerFileInputNewForFileContext}*/}
                    {/*        title="Add file"*/}
                    {/*        disabled={currentFileContextLength >= MAX_FILES}*/}
                    {/*>*/}
                    {/*    <div>Add Files</div>*/}
                    {/*    <FaPlus />*/}
                    {/*</button>*/}
                    <div>{`${currentFileContextLength}/${MAX_FILES} files`}</div>
                    <div className={'fa-icon -blue'}
                            onClick={triggerFileInputNewForFileContext}
                            title="Add file"
                            // disabled={currentFileContextLength >= MAX_FILES}
                    >
                        {/*<div>Add Files</div>*/}
                        <FaPlus />
                    </div>
                </div>
            </div>
            <div>
                <input
                    type="file"
                    style={{display: 'none'}}
                    ref={fileInputRefNew}
                    onChange={handleFileChangeNewForFileContext}
                    multiple
                />
            </div>
        </div>
        {filesListDiv}
        {fileContextSwitchModal}
        {newFileContextModal}
        {editContextModal}
        {loading && <Busy/>}
    </div>
}

export default FileContextTop;
