import React, {useState, useEffect, useContext, useRef} from 'react';
import styles from "./SystemMessageEditor.module.css";
import {setCurrentChatId, setInfoMessage} from "../../redux/actions";
import {AppContext} from "../../redux/AppContext";
// import { getApi, getToken } from '../../services/apiService';
import {useMsal} from "@azure/msal-react";
import {ThemeContext} from "../../redux/ThemeContext";
import Busy from "../Busy/Busy";
import {useApi} from "../../hooks/useApi";
import {FaArrowRight, FaLanguage, FaWandMagicSparkles} from "react-icons/fa6";
import {FaRegCheckCircle, FaRegTimesCircle, FaUndo} from "react-icons/fa";
import {AiOutlineLoading3Quarters} from "react-icons/ai";
import {uploadDocumentsUsingS3} from "../Chat/FileUploader";
import {TbFileSpark} from "react-icons/tb";

function SystemMessageEditor( {messageId = null, callbackOnSave=null}) {
    const [sysMessageText, setSysMessageText] = useState('');
    const [promptText, setPromptText] = useState('');
    const [responseText, setResponseText] = useState(null);
    const [title, setTitle] = useState('');
    const { state, dispatch } = useContext(AppContext);
    const { currentProject, useDataStore, useModel } = state;
    const [loading, setLoading] = useState(false);
    const { instance } = useMsal();
    const [candidateSysMessageText, setCandidateSysMessageText] = useState(null);
    const { theme } = useContext(ThemeContext);
    const [undoText, setUndoText] = useState(null);
    const fileInputRefNew = useRef(null);
    const [promptFile, setPromptFile] = useState(null)

    const api = useApi();

    useEffect(()=> {
        if (messageId) {
            console.log( 'messageId: ', messageId);
            api.get(`/api/system_messages/${messageId}`, {
                params: {
                    project_id: currentProject.id
                }
            }).then(response => {
                setSysMessageText( response.data.content);
                setTitle( response.data.title);
            })
            .catch((error)=> { /*error handled in apiService*/});
        }
    }, [messageId])

    // const [loading, setLoading] = useState(false);
    const handleSave = async () => {
        setLoading(true);
        try {
            if (messageId == null) {
                const response = await api.post('/api/system_messages',
                    {
                        type: 'context', content: sysMessageText,
                        title: title,
                        project: currentProject.id,
                        is_shared: false
                    }
                );
            } else {
                const response = await api.put(`/api/system_messages/${messageId}`,
                    {
                        type: 'context', content: sysMessageText,
                        title: title,
                        project: currentProject.id,
                        is_shared: false
                    }
                );
            }
            dispatch( setInfoMessage('Saved!'));
            if (callbackOnSave) {
                callbackOnSave(true);
            }
        } catch (error) {
            console.error('Error creating system messages', error);
        } finally {
            setLoading(false);
        }
    }

    const handleSend = () => {
        const request = {  // first message
            message: promptText,
            use_model: useModel,
            system_message: sysMessageText,
            // temperature: temperature,
        };
        if (promptFile?.file_url) {
            request['image_url'] = promptFile.file_url
        }
        setLoading(true);
        api.post('/api/chat/message/simple', request)
            .then(async response => {
                setResponseText( response.data.response);
            })
            .catch((error)=> { /*error handled in apiService*/})
            .finally(() => {
                setLoading(false);
            });
    };

    const handleFileInputNew = async (file) => {
        const response = await uploadDocumentsUsingS3(api,
            file,
            currentProject.id,
            null);
        setPromptFile({
            file_url: response.file_url,
            file_name: file.name,
            content_type: response.content_type,
        })
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

    const handleDropFilesNew = async (dropFiles) => {
        console.log( 'dropFilesNew', dropFiles);
        if (dropFiles.length<= 0) return;
        try {
            setLoading(true);
            for (let i = 0; i < dropFiles.length; i++) {
                await handleFileInputNew(dropFiles[i]);
            }
            // moveScrollToEnd();
        } catch (error) {
            console.error('Error uploading file:', error);
        } finally {
            setLoading(false);
        }
    };

    const handleFileChangeNew = async (event) => {
        const file = event.target.files[0];
        if (!file) {
            console.log( 'No file selected!', file);
            return;
        }

        await handleDropFilesNew(event.target.files);
        event.target.value = "";
    };

    const triggerFileInputNew = () => {
        fileInputRefNew.current.click();
    };

    const translate = () => {
        if (!sysMessageText) return;

        setLoading(true);
        api.post(`/api/llm_task/translate`, {
            prompt: sysMessageText
        }).then(response => {
            setCandidateSysMessageText( response.data);
        })
        .catch((error)=> { /*error handled in apiService*/})
        .finally(() => {
            setLoading(false);
        });
    }

    const improve_prompt = () => {
        if (!sysMessageText) return;

        setLoading(true);
        api.post(`/api/llm_task/improve_prompt`, {
            prompt: sysMessageText
        }).then(response => {
            setCandidateSysMessageText( response.data);
        })
        .catch((error)=> { /*error handled in apiService*/})
        .finally(() => {
            setLoading(false);
        });
    }

    const candidateDiv = candidateSysMessageText && (
        <div className={styles['candidate-window']}>
            <div className={`${styles['candidate-output-container']} code-view`}>
                {candidateSysMessageText}
            </div>
            <div className={styles['candidate-panel']}>
                <div
                        className={`fa-icon -larger-xx`}
                        onClick={(event) => {
                            setCandidateSysMessageText(null)
                        }}
                        title={"reject"}
                >
                    <FaRegTimesCircle/>
                    {/*<img*/}
                    {/*    src={theme == "dark" ? "/icons8-cancel-50-dark.png" : "/icons8-cancel-50-light.png"}*/}
                    {/*/>*/}
                </div>
                <div
                        className={`fa-icon -larger-xx -accept`}
                        onClick={(event) => {
                            setSysMessageText(candidateSysMessageText);
                            setUndoText(sysMessageText);
                            setCandidateSysMessageText(null);
                        }}
                        title={"accept"}
                >
                    <FaRegCheckCircle/>
                    {/*<img*/}
                    {/*    src={theme == "dark" ? "/icons8-accept-50-green-dark.png" : "/icons8-accept-50-blue-light.png"}*/}
                    {/*/>*/}
                </div>
            </div>
        </div>
    )

    return (
        <div className={styles['container']}>
            <div className={styles['workspace']}>
                <div className={styles['workspace-left']}>
                    <div className={styles['system-message-edit-space']}>
                        <textarea
                            autoFocus
                            placeholder="Enter your system message"
                            value={sysMessageText}
                            className={`code ${styles["system-message-textarea"]}`}
                            onChange={e => setSysMessageText(e.target.value)}
                        />
                    </div>
                </div>
                <div className={styles['workspace-right']}>
                    <div className={styles['prompt-panel']}>
                        <div className={"fa-icon -larger"}
                             onClick={triggerFileInputNew}
                             title="Attach any file  (use is model dependent!)"
                        >
                            <TbFileSpark />
                            <input
                                type="file"
                                style={{display: 'none'}}
                                ref={fileInputRefNew}
                                onChange={handleFileChangeNew}
                                multiple
                            />
                        </div>
                        {/*{JSON.stringify(promptFile)}*/}
                        {promptFile?.file_url && <div className={styles["image-icon"]}>
                            <img src = {promptFile?.file_url}/></div>}
                    </div>
                    <div className={styles['prompt-container']}>
                        <textarea
                            value={promptText}
                            placeholder="Test your system message. Input a user prompt..."
                            className={`code ${styles["prompt-textarea"]}`}
                            onChange={e => setPromptText(e.target.value)}
                        />
                        <div
                                className={`fa-icon -blue  ${loading?"loading-anim":""}`}
                                onClick={(event) => {
                                    handleSend();
                                }}
                                // disabled={loading}
                        >
                            {loading? <AiOutlineLoading3Quarters/>: <FaArrowRight/>}

                            {/*<img*/}
                            {/*    src={theme == "dark" ? "/icons8-right-arrow-blue-50--dark.png" : "/icons8-right-arrow-blue-50--light.png"}*/}
                            {/*/>*/}
                        </div>
                    </div>
                    <div className={`${styles['chat-output-container']}`}>
                        <div className={`${styles['chat-output-content']} code-view`}>
                            {responseText}
                        </div>
                    </div>
                </div>
                {candidateDiv}
            </div>
            <div className={styles['workspace-panel']}>
                {undoText && <div
                    className={`fa-icon`}
                    onClick={(event) => {
                        const tmp = sysMessageText;
                        setSysMessageText(undoText);
                        setUndoText(tmp);
                    }}
                    title={"Undo"}
                    >
                    <FaUndo/>
                    {/*<img*/}
                    {/*    src={theme == "dark" ? "/icons8-undo-50--dark.png" : "/icons8-undo-50--light.png"}*/}
                    {/*/>*/}
                    </div>
                }
                <div
                    className={"fa-icon"}
                    onClick={(event) => {
                        translate()
                    }}
                    // disabled={loading}
                    title={"Translate to English"}

                >
                    <FaLanguage/>
                    {/*<img*/}
                    {/*    src={theme == "dark" ? "/icons8-translate-50-dark.png" : "/icons8-translate-50-light.png"}*/}
                    {/*/>*/}
                </div>
                <div
                        className={`icon-button`}
                        onClick={(event) => {
                            improve_prompt()
                        }}
                        // disabled={loading}
                        title={"Improve my prompt!"}
                >
                    <FaWandMagicSparkles/>

                    {/*<img*/}
                    {/*    src={theme == "dark" ? "/icons8-magic-wand-dark.png" : "/icons8-magic-wand-light.png"}*/}
                    {/*/>*/}
                </div>
            </div>
            <div className={styles["title-panel"]}>
                <div className={styles["title-panel-left"]}>
            Name: <input type={"text"} className={`${styles["title-text"]} input`}
                                    value={title}
                                    onChange={e => setTitle(e.target.value)}/>
                </div>
                <div>
                    <button
                        onClick={() => handleSave()}
                        className="button"
                        disabled={!title}
                    >Save</button>
                </div>
            </div>
            {loading && <Busy/>}
        </div>
    )
}


export default SystemMessageEditor;
