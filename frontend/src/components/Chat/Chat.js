import React, {useContext, useEffect, useLayoutEffect, useMemo, useRef, useState} from 'react';
import styles from './Chat.module.css';
import config from "../../config";
import MaxModal from "../MaxModal/MaxModal"
import {AppContext} from "../../redux/AppContext";
import {
    setBalance,
    setCodeEditor, setCurrentChatId,
    setCurrentUsage,
    setDisableFromat,
    setErrorMessage,
    setForceRefreshHistory,
    setInfoMessage,
    setResizeDetected,
    setShowOnTop
} from "../../redux/actions";
import {ThemeContext} from "../../redux/ThemeContext";
import {useNavigate, useParams} from "react-router-dom";
import Busy from "../Busy/Busy";
import ContextModal from "../ContextModal/ContextModal";
import DragAndDrop from "../DragAndDrop/DragAndDrop";
import FullMarkdown from "../FullMarkdown/FullMarkdown";
import AssistantWrapper from "../AssistantWrapper/AssistantWrapper";
import {useApi} from "../../hooks/useApi";
import {
    FaCheck,
    FaEdit,
    FaFileAlt,
    FaRegCheckCircle,
    FaRegTimesCircle,
    FaRobot,
    FaShareAlt,
    FaUndo,
    FaUser
} from "react-icons/fa";
import {
    FaArrowDown,
    FaArrowRight,
    FaBookmark,
    FaCopy,
    FaDisplay,
    FaDownload,
    FaLanguage,
    FaPlus,
    FaRegBookmark,
    FaTrash,
    FaWandMagicSparkles
} from "react-icons/fa6";
import {IoCodeOutline} from "react-icons/io5";
import {
    MdCode,
    MdCodeOff,
    MdOutlineKeyboardArrowLeft,
    MdOutlineKeyboardArrowRight,
    MdOutlineKeyboardDoubleArrowRight
} from "react-icons/md";
import {Title} from "../Headings/Heading";
import {LuArrowUpToLine} from "react-icons/lu";
import PromptEditor from "./PromptEditor";
import {TiDocumentText} from "react-icons/ti";
import {TbFileSpark, TbFishBone, TbHistory} from "react-icons/tb";
import {uploadDocumentsUsingS3} from "./FileUploader";
import MessageCard from "./MessageCard";
import {keyFor, reasoningEffortPreferenceKey} from "../../preferences";

const formatChatThread = (messages, isDisableFormat) => {
    return (messages || []).map((message, index) => {
        if (message.role === "assistant" && !isDisableFormat) {
            return {
                ...message,
                formatted: <div className={styles["markdown-parent"]}><FullMarkdown content={message.content}/></div>
            }
        } else {
            return message
        }
    })
};

const printRender =(() => {
    let count = 0;
    return () => {
        count += 1;
        console.log(count, new Date());
    };
})();

const temporary_guid = () => {
    return null;
    // return `tmp-${Math.random().toString(36).substring(2, 15)}`;
}

const MAX_ALTERNATIVES = 7

function Chat() {
    const [messages, setMessages] = useState([]);
    const [title, setTitle] = useState('');
    const [createdAt, setCreatedAt] = useState(null);
    const inputValueRef = useRef('');
    const [systemMessages, setSystemMessages] = useState([]);
    const [contextSnippets, setContextSnippets] = useState([]);
    const [lastPrompts, setLastPrompts] = useState([]);
    const [isOwner, setIsOwner] = useState(false);
    const { state, dispatch } = useContext(AppContext);
    const { currentProject, isMobile, useModel, useSearch, useCode, chatLayout,
        modelList, isDisableFormat, showOnTop, isCodeEditor, useImageGeneration,
        useModelAlternatives, showMultiColumn, preferences, currentFileContext, temporaryChat } = state;
    const { chatIdFromUrl  } = useParams();
    const chatId = typeof(chatIdFromUrl) == 'object'? chatIdFromUrl?.chatIdFromUrl: chatIdFromUrl;
    const [loading, setLoading] = useState(false);
    const chatEndRef = useRef(null);
    const navigate = useNavigate();
    const [chatInfo, setChatInfo] = useState({
        is_bookmarked: false,
        estimateCost: undefined
    })
    const lastMessageRef = useRef(null);
    const fileInputRefNew = useRef(null);
    const [showSharedModal, setShowSharedModal] = useState(false);
    const [shareLoading, setShareLoading] = useState(false);
    const [sharedId, setSharedId] = useState(null);
    const [sharedList, setSharedList] = useState([]);
    const sendButtonRef = useRef(null);
    const [lastIncrement, setLastsIncrement] = useState(0);
    const [flgIncrement, setFlgIncrement] = useState(0);
    const [candidateInput, setCandidateInput] = useState(null);
    const [undoInput, setUndoInput] = useState(null);
    // const [resubmitParameters, setResubmitParameters] = useState();
    const [focusEntryIndex, setFocusEntryIndex] = useState(null);
    const api = useApi();
    // const [onTop, setOnTop] = useState(true);
    const promptEditorRef = useRef(null);
    const [viewSize, setViewSize] = useState(localStorage.getItem('viewSize')==null?1:parseInt(localStorage.getItem('viewSize')),);
    // const [resubmitModelList, setResubmitModelList] = useState(['', '', '']);
    const [modelListFirstEmpty, setModelListFirstEmpty] = useState([]);
    // const [chatId, setChatId] = useState(null);
    const [projectMismatch, setProjectMismatch] = useState(false);
    const [undoViewSize, setUndoViewSize] = useState(1);
    // const [useMulti, setUseMulti] = useState(false);
    const [alternativeRetryParameters, setAlternativeRetryParameters] = useState(null);
    // const [version, bumpVer] = useState(0);
    const [contextHistoryModalClickPosition, setHistoryListModalClickPosition] = useState(null);

    useEffect(()=> {
        if (messages.length> 0 && flgIncrement !== lastIncrement) {
            moveScrollToLastMsg();
            // moveScrollToEnd();
            // inputRef?.current?.focus();
            setLastsIncrement(flgIncrement);

        }
    }, [messages])

    // Memoize the formatted messages
    const formattedMessages = useMemo(
        () => formatChatThread(messages, isDisableFormat), [messages, isDisableFormat]);

    useEffect(()=> {
        loadSystemMessages();
        loadSnippets();
    }, []);

    const setLatestInput = (v) => {
        inputValueRef.current = v;
        promptEditorRef.current?.setValue(v);
    }

    const onTop =!messages || messages.length<= 0;

    const useMulti =  messages.some(
        m => Array.isArray(m) && m.length > 1
    );


    useEffect(() => {
        // console.log( 'chatId modified to ', chatId);
        if (!chatId) return;

        // navigate(`/chat/${chatId}`, { replace: true }); // use replace to not push extra history
        loadChatThread();

        setSharedId(prev => (prev!== null? null: prev));
        // setResubmitParameters(prev => (prev!== null? null: prev));  //clear
    }, [chatId]);

    useEffect(()=> {
        setModelListFirstEmpty([{name:''}].concat(modelList))
    }, [modelList])

    useEffect(()=> {
        dispatch(setResizeDetected(new Date()));
    }, [chatLayout, viewSize]);


    const computedTitle = "Limits of Imagery..."

    useEffect(() => {
        document.title = computedTitle;
    }, [computedTitle]);

    // useEffect(()=> {
    //     const hasMulti = messages.some(
    //         m => Array.isArray(m) && m.length > 1
    //     );
    //     setUseMulti(hasMulti);
    // }, [messages])


    const moveScrollToEnd= () => {
        setTimeout(() => {
            chatEndRef?.current?.scrollIntoView({ behavior: "smooth" });
        }, 10);
    }
    const moveScrollToTop= () => {
        setTimeout(() => {
            window.scrollTo({
                top: 0,
                left: 0,
                behavior: 'smooth' // for smooth scrolling
            });

        }, 10);
    }

    const moveScrollToLastMsg = () => {
        setTimeout(()=> {
            // https://stackoverflow.com/questions/11039885/scrollintoview-causing-the-whole-page-to-move
            // lastMessageRef?.current?.scrollIntoView({ behavior: 'smooth'});
            // lastMessageRef?.current?.scrollIntoView({ behavior: 'smooth', block: 'start'});
            if (isMobile) {
                lastMessageRef?.current?.scrollIntoView({ behavior: 'smooth', block: 'start'});
            } else {
                lastMessageRef?.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest'});
                // chatEndRef?.current?.scrollIntoViewIfNeeded(false);
            }
        }, 100);
    }

    const getLayoutSensitiveClassName = (baseClass) => {
        if (isMobile) {
            return `${styles[baseClass]} ${styles[`${baseClass}--bottom`]}`;
        }
        return `${styles[baseClass]} ${chatLayout === "side" ? styles[`${baseClass}--side`] : styles[`${baseClass}--bottom`]}`;
    };

    const augmentUseModelListWithPreferences = (useModelList) => {
        return useModelList.map((m) => {
            const model = {
                name: m
            }
            if (reasoningEffortPreferenceKey(m) in preferences) {
                model['reasoning_effort'] = preferences[reasoningEffortPreferenceKey(m)]
            }
            if (keyFor(m, "use_search") in preferences) {
                model["use_search"] = true;
            }
            if (keyFor(m, "use_code") in preferences) {
                model["use_code"] = true;
            }
            if (keyFor(m, "use_image_generation") in preferences) {
                model["use_image_generation"] = true;
            }
            return model;
        })
    }


    const loadSnippets = async () => {
        // const response = await api.get('/api/context_artifacts', {
        //     params: {
        //         project_id: currentProject.id,
        //         titles_only: true
        //     }
        // })
        // setContextSnippets(response.data);
    }

    const loadSystemMessages = () => {
        // api.get('/api/system_messages', {
        //     params: {
        //         project_id: currentProject.id
        //     }
        // }).then(response => {
        //     const loadedSystemMessages = response.data;
        //     setSystemMessages(loadedSystemMessages);
        // })
        // .catch((error)=> { /*error handled in apiService*/});
    }

    const loadChatThread = (fullLoad= true) => {
        if (chatId) {

            const skip = fullLoad?0: messages.filter( m=> Array.isArray(m)).length;
            api.get(`/api/chats/${chatId}/thread`, {
                params: {
                    skip: skip,
                }
            })
                .then(response => {
                    if (response.data.project_id && response.data.project_id!= currentProject.id) {
                        console.log('** projectMismatch! current: ', currentProject.id, "current chat:", response.data.project_id, response.data);
                        setProjectMismatch(true);
                        dispatch(setErrorMessage("project mismatch"));
                    } else {
                        setProjectMismatch(false);
                    }

                    setMessages(prevMessages => fullLoad ?
                        response.data.entries :
                        [...prevMessages.filter(m=>Array.isArray(m)), ...response.data.entries]);
                    setChatInfo(response.data)
                    setTitle(response.data.title);
                    setCreatedAt(response.data?.created_at);
                    setIsOwner(response.data.isOwner);
                })
                .catch((error) => { /*error handled in apiService*/
                });
        }
    }

    const onControlEnter = ()=> {
        if (sendButtonRef.current) {
            sendButtonRef.current.click();
        }
    }

    const handleSend = async (event) => {
        handleSendApi()
    }

    const updateMetric = () => {
        // api.get('/api/metrics/monthly_usage/current')
        //     .then(response => {
        //         dispatch(setCurrentUsage(response.data));
        //     })
        //     .catch((error)=> { /*error handled in apiService*/});

        // api.get("/api/account/balance")
        //     .then(response => {
        //         dispatch(setBalance(response?.data));
        //     })
        //     .catch((error)=> { /*error handled in apiService*/});
    }

    const handleSendApi = (pInput) => {
        if (loading) return;
        const prompt = inputValueRef.current || pInput;
        if (!prompt) return;

        let presetList = messages.filter(m=>
            !Array.isArray(m) && (m.entry_id == null || m.entry_id.startsWith('tmp-'))
        ).map(m=> { return {
            role: m.role,
            content: m.content,
            image_url: m?.image_url,
            file_url: m?.file_url,
            file_name: m?.file_name,
            content_type: m?.content_type,
        }})

        let _useModel = augmentUseModelListWithPreferences([useModel, ...useModelAlternatives])
        if (temporaryChat) {           
            _useModel = [_useModel[0]];
        }
        const isNewChat = !chatId
        const request = chatId ? {   // not first message
            message: inputValueRef.current || pInput,
            use_model: _useModel,
            chat_id: chatId,
            temporary_chat: temporaryChat,
            preset_list: presetList,
            project_id:  currentProject.id,
            file_context_id: currentFileContext?.id,
        } : {  // first message
            message: inputValueRef.current || pInput,
            use_model: _useModel,
            preset_list: presetList,
            chat_id: null,
            temporary_chat: temporaryChat,
            project_id:  currentProject.id,
            file_context_id: currentFileContext?.id,
        };
        setLoading(true);
        // setChatLoading(true);
        api.post('/api/chat/message', request)
            .then(async response => {
                setLatestInput('');
                setUndoInput('');

                if (temporaryChat) {   //for temporary chat don't load the chat thread
                    const entries = response.data?.entries.map(entry => ({
                        ...entry,
                        entry_id: temporary_guid()
                    }));
                    setMessages(prevMessages => [
                        ...prevMessages,
                        {
                            role: "user",
                            content: request.message,
                            entry_id: temporary_guid()
                        }, 
                        ...entries
                    ]);
                } else {
                    loadChatThread(isNewChat);
                    dispatch(setForceRefreshHistory(new Date()));
                }
                updateMetric();
                setFlgIncrement(prevState => prevState+1);
                if (response.data?.errors) {
                    dispatch(setErrorMessage(response.data?.errors));
                }
            })
            .catch((error)=> { /*error handled in apiService*/})
            .finally(() => {
                setLoading(false);
            });
    };

    const handleBranchInNewChat = async (entryId) => {
        const request = {   // not first message
            chat_id: chatId,
            entry_id: entryId,
            project_id:  currentProject.id,
        };
        setLoading(true);
        api.post('/api/chat/message/branch-in-new-chat', request)
            .then(async response => {
                const newChatId = response?.data;
                await dispatch(setCurrentChatId(newChatId))
                navigate(`/chat/${newChatId}`);
            })
            .catch((error)=> { /*error handled in apiService*/})
            .finally(() => {
                setLoading(false);
            });
    }


    const handleSubmitAlternativeRetry = async () => {
        if (loading) return;
        const request = {   // not first message
            message: "(ignore)",
            use_model: augmentUseModelListWithPreferences([alternativeRetryParameters.model]),
            chat_id: chatId,
            retry_entry_id: alternativeRetryParameters.entry_id,
            project_id:  currentProject.id,
            file_context_id: currentFileContext?.id,
            // options: {
            //     use_search: useSearch,
            //     use_code: useCode,
            //     // use_url_context: useUrlContext,
            //     use_image_generation: useImageGeneration
            // }
        };
        setLoading(true);
        api.post('/api/chat/message', request)
            .then(async response => {
                loadChatThread();  //full load
                dispatch(setForceRefreshHistory(new Date()));
                updateMetric();
                setFlgIncrement(prevState => prevState+1);
                setAlternativeRetryParameters(null);
            })
            .catch((error)=> { /*error handled in apiService*/})
            .finally(() => {
                setLoading(false);
            });
    }

    const handleAlternativeRetry = async (pos, index, entry_id) => {
        setLoading(true);
        try {
            setAlternativeRetryParameters({
                pos,
                index,
                entry_id,
            })
        } finally {
            setLoading(false);
        }
    }

    const handleSelectSystemMessage = async (index) => {
        setMessages(current => [...current, {
            role: "system",
            content: systemMessages[index].content,
            preset_id: systemMessages[index].id,
            entry_id: null,
        }]);
    };

    const handleTouchSystemMessage= async (index) => {
        try {
            await api.put(`/api/system_messages/${systemMessages[index].id}/touch`);
            loadSystemMessages();
        } finally {
        }
    }
    const handleDeleteSystemMessage= async (index) => {
        if (!window.confirm(`Delete system message: ${systemMessages[index].title} ?`))
            return;
        try {
            await api.delete(`/api/system_messages/${systemMessages[index].id}`);
            loadSystemMessages();
        } finally {
        }
    }

    const handleAddEmptyMessage = () => {
        setMessages(current =>  [...current, {
            role: "user",
            content: "",
            entry_id: null,
        }]);
    }
    const handleAddEmptySystemMessage = () => {
        setMessages(current =>  [...current, {
            role: "system",
            content: "",
            entry_id: null,
        }]);
    }

    const handleSelectSnippet = async (index, event) => {
        setLoading(true);
        try {
            const response = await api.get(`/api/context_artifacts/${contextSnippets[index].id}`)
            setMessages(current => [...current, {
                role: "user",
                content: response.data?.content,
                preset_id: contextSnippets[index].id,
                entry_id: null,
            }]);
        } finally {
            setLoading(false);
        }
    };

    const handleSelectLastPrompt = async (index, event) => {
        setLoading(true);
        try {
            const response = await api.get(`/api/last_prompts/${lastPrompts[index].id}`)
            setMessages(current => [...current, {
                role: "user",
                content: response.data?.content,
                preset_id: lastPrompts[index].id,
                entry_id: null,
            }]);
        } finally {
            setLoading(false);
        }

    }

    const handleTouchSnippet = async (index) => {
        await api.put(`/api/context_artifacts/${contextSnippets[index].id}/touch`);
        await loadSnippets();
    }
    const handleDeleteSnippet = async (index) => {
        if (!window.confirm(`Delete [${contextSnippets[index].title}] ?`))
            return;
        try {
            await api.delete(`/api/context_artifacts/${contextSnippets[index].id}`);
            loadSnippets();
        } finally {
        }
    }

    const handleDeleteEntry = async (entryId) => {
        try {
            setLoading(true);
            await api.delete(`/api/chats/${chatId}/entry/${entryId}`);
            await loadChatThread()
        } finally {
            setLoading(false);
        }
    }


    const handleMakeAlternativeMain = async (entryId) => {
        try {
            setLoading(true);
            await api.put(`/api/chats/${chatId}/entry/${entryId}/make-alternative-main`);
            await loadChatThread()
        } finally {
            setLoading(false);
        }
    }

    const handleDeletePresetEntry = async (index) => {
        const message = messages[index];
        if (message?.file_url || message?.image_url) {
            try {
                setLoading(true);
                await api.delete(`/api/upload`, {params: {file_url: message?.file_url || message?.image_url}});
            } finally {
                setLoading(false);
            }
        }
        setMessages(prevMessages => {
            const newMessages = [...prevMessages];
            newMessages.splice(index, 1);
            return newMessages;
        });
    }

    const handleSwitchRole = (index, role) => {
        setMessages(prevMessages => {
            const newMessages = [...prevMessages];
            newMessages[index].role=role;
            return newMessages;
        });
    }

    const handleCopyContent = (content) => {
        if (navigator.clipboard) {
            navigator.clipboard.writeText(content).then(() => {
                console.log('Content copied to clipboard');
                dispatch( setInfoMessage('Content copied to clipboard'));
            }).catch(err => {
                console.error('Could not copy text: ', err);
            });
        } else {
            setErrorMessage( "Not supported in this browser");
        }
    };

    const handleMakeShared = async () => {
        setShareLoading(true);
        try {
            const response = await api.put(`/api/chats/${chatId}/make_shared`);
            setSharedId( response.data?.shared_id);
            handleCopyContent(sharedIdToUrl(response.data?.shared_id));
        } finally {
            setShareLoading(false);
        }
    }


    const handleLoadShared = async () => {
        api.get('/api/shared_chats', {
            params: {
                project_id: currentProject.id,
            }
        }).then(response => {
            setSharedList(response.data);
        })
        .catch((error)=> { /*error handled in apiService*/});
    }

    const handleDeleteShared = (shared_id) => {
        api.delete(`/api/shared_chats/${shared_id}`, {
            params: {
                project_id: currentProject.id,
            }
        }).then(response => {
            handleLoadShared();
        })
        .catch((error)=> { /*error handled in apiService*/});
    }

    const sharedIdToUrl = (shared_id) => {
        return `${config.frontendUrl}/#/shared/${shared_id}`
    }

    const sharedModal = showSharedModal && (
        <MaxModal show={showSharedModal} handleClose={()=> setShowSharedModal(false)}>
            <div>
                <div className={"title"}>Create a public link to share</div>
                <div className={styles["share-message"]}>Anyone with the link can see or share it with others, so share
                    responsibly.
                </div>
                <div className={styles["share-panel"]}>
                    <a className={styles["make-shared"]} onClick={(event) => handleMakeShared()}>
                        Create public link</a>
                    {shareLoading && <div>Loading...</div>}
                </div>

                {sharedId && (
                    <div className={styles["share-panel-result"]}>
                        <div className={`${styles["share-link"]} code-view`}>
                            {sharedIdToUrl(sharedId)}
                        </div>
                        <div onClick={() => handleCopyContent(sharedIdToUrl(sharedId))}
                             className="fa-icon">
                            <FaCopy/>
                        </div>
                    </div>)}

                <hr/>
                <div className={styles["share-panel"]}>
                    <a className={styles["make-shared"]} onClick={(event) => handleLoadShared()}>
                        Load my shared links</a>
                </div>
                {sharedList && (
                    <div className={styles["shared-list"]}>
                        {sharedList.map((d, index) => (
                            <div className={styles["shared-list-line"]} key={index}>
                                <div>{d.title}</div>
                                <div>{new Date(d.shared_id_expire_date).toDateString()}</div>
                                <div onClick={() => handleDeleteShared(d.shared_id)}
                                     className="fa-icon" title={"delete"}>
                                    <FaTrash/>
                                </div>
                                <div onClick={() => handleCopyContent(sharedIdToUrl(d.shared_id))}
                                                                      className="fa-icon" title={"copy shared link"}>
                                    <FaCopy/>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </MaxModal>
    )

    const triggerFileInputNew = () => {
        fileInputRefNew.current.click();
    };

    const handleDropFilesNew = async (dropFiles) => {
        console.log( 'dropFilesNew', dropFiles);
        if (dropFiles.length<= 0) return;
        try {
            setLoading(true);
            for (let i = 0; i < dropFiles.length; i++) {
                await handleFileInputNew(dropFiles[i]);
            }
            moveScrollToEnd();
        } catch (error) {
            console.error('Error uploading file:', error);
        } finally {
            setLoading(false);
        }
    };

    const handleFileInputNew = async (file) => {
        const response = await uploadDocumentsUsingS3(api, file, currentProject.id, chatId);
        setMessages(current =>  [...current, {
            role: "user",
            content: null,
            // preset_id:  response.data.file_url,
            file_url: response.file_url,
            file_name: file.name,
            content_type: response.content_type,
            entry_id: null,
        }]);
    }

    const handleFileChangeNew = async (event) => {
        const file = event.target.files[0];
        if (!file) {
            console.log( 'No file selected!', file);
            return;
        }

        await handleDropFilesNew(event.target.files);
        event.target.value = "";
    };


    const undo = () => {
        if (!undoInput) return;

        const tmp = inputValueRef.current;
        setLatestInput(undoInput);
        setUndoInput(tmp);
    }

    const translate = () => {
        if (!inputValueRef.current) return;
        setLoading(true);
        api.post(`/api/llm_task/translate`, {
            prompt: inputValueRef.current
        }).then(response => {
            setCandidateInput( response.data);
        })
            .catch((error)=> { /*error handled in apiService*/})
            .finally(() => {
                setLoading(false);
            });
    }

    const improve_prompt = () => {
        if (!inputValueRef.current) return;

        setLoading(true);
        api.post(`/api/llm_task/improve_prompt`, {
            prompt: inputValueRef.current
        }).then(response => {
            setCandidateInput( response.data);
        })
            .catch((error)=> { /*error handled in apiService*/})
            .finally(() => {
                setLoading(false);
            });
    }

    const candidateInputDiv = candidateInput && (
        <div className={styles['candidate-window']}>
            <div className={`${styles['candidate-output-container']} code-view`}>
                {candidateInput}
            </div>
            <div className={styles['candidate-panel']}>
                <div
                    // type="submit"
                        className={`fa-icon -larger-xx`}
                        // className={`${isMobile? "icon-button-larger": "icon-button-larger"}`}
                        onClick={(event) => {
                            setCandidateInput(null)
                        }}
                        title={"Reject"}
                >
                    <FaRegTimesCircle/>
                </div>
                <div
                        className={`fa-icon -larger-xx -accept`}
                        onClick={(event) => {
                            setUndoInput(inputValueRef.current);
                            setLatestInput(candidateInput);
                            setCandidateInput(null);
                        }}
                        title={"Accept and replace the current prompt"}
                >
                    <FaRegCheckCircle/>
                </div>
            </div>
        </div>
    )

    const undoButton = (<div
        className={`fa-icon ${isMobile? styles["input-view-icon"]:""}`}
        onClick={(event) => {
            undo()
        }}
        title={"Undo suggested prompt"}
    >
        <FaUndo/>
    </div>)

    const translateButton = (<div
                                     className={`fa-icon -larger ${isMobile? styles["input-view-icon"]:""}`}
                                     onClick={(event) => {
                                         translate()
                                     }}
                                     title={"Translate to English"}
    >
        <FaLanguage/>
    </div>)

    const codeEditorButton = (<div
        className={`fa-icon -larger ${isMobile? styles["input-view-icon"]:""}`}
        onClick={(event) => {
            dispatch(setCodeEditor(!isCodeEditor));
        }}
        title={isCodeEditor? "text editor": "code editor"}
    >
        {isCodeEditor? <TiDocumentText/>: <IoCodeOutline />}
    </div>)


    const switchViewSizeLeftButton = (<div
        className={`fa-icon ${isMobile? styles["input-view-icon"]:""}`}
        onClick={(event) => {
            // console.log( viewSize);
            const newValue= Math.min(4, viewSize+1);
            setViewSize(newValue);
            localStorage.setItem('viewSize', ""+newValue);
        }}
        title={"switch view size"}
    >
        <MdOutlineKeyboardArrowLeft  />
    </div>)

    const switchViewSizeRightButton = (<div
        className={`fa-icon ${isMobile? styles["input-view-icon"]:""}`}
        onClick={(event) => {
            const newValue= Math.max(0, viewSize-1);
            setViewSize(newValue);
            localStorage.setItem('viewSize', ""+newValue);
        }}
        title={"switch view size"}
    >
        <MdOutlineKeyboardArrowRight  />
    </div>)

    const switchViewSizeRightMostButton = (<div
        className={`fa-icon ${isMobile? styles["input-view-icon"]:""}`}
        onClick={(event) => {
            setUndoViewSize(viewSize);
            const newValue= 0;
            setViewSize(newValue);
            localStorage.setItem('viewSize', ""+newValue);
        }}
        title={"switch view size"}
    >
        <MdOutlineKeyboardDoubleArrowRight  />
    </div>)


    // const improvePromptButton = (<div
    //             className={`fa-icon ${isMobile? styles["input-view-icon"]:""}`}
    //             onClick={(event) => {
    //                 improve_prompt()
    //             }}
    //             title={"Improve my prompt!"}
    //     >
    //         <FaWandMagicSparkles/>
    //     </div>)

    // const readyToSend = inputValueRef.current || messages.some(m=> m.entry_id==null && m.role === "user");

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
            const files = []
            for (let item of clipboardItems) {
                // if (item.kind === "file" && item.type.startsWith("image/")) {
                if (item.kind === "file") {
                    files.push(item.getAsFile());
                    // const file = item.getAsFile();
                    // await handleFileInputNew(file);
                    imagePasted = true;
                }
            }

            for (let f of files) {
                await handleFileInputNew(f);
            }

            // Prevent Monaco Editor from inserting "image.png" or similar text
            if (imagePasted) {
                console.log("Stop propagation");
                event.preventDefault();  // Stop default paste behavior
                event.stopPropagation(); // Stop Monaco from handling it further
                moveScrollToEnd();
            }
        } catch (error) {
            console.error('Error uploading file:', error);
        } finally {
            setLoading(false);
        }
    }


    const promptEditor = (
        <PromptEditor
            // version={version}
            ref={promptEditorRef}
            defaultValue={inputValueRef.current}
            onValueChange={(v)=> {inputValueRef.current = v;}}
            onWillUnmount={(v) => {inputValueRef.current = v;}}
            onControlEnter={() => onControlEnter()}
            // isCodeEditor={isMobile?false:(chatLayout==="side"?isCodeEditor:false)}
            isCodeEditor={isMobile?false:isCodeEditor}
            onDidPaste={onDidPaste}
            chatLayout={chatLayout}
            showMinMap={chatLayout==="bottom"}
        />
    )

    const chatInputPanel = (
        <>
            {isMobile  && (
                <div className={`${styles["chat-bottom"]} ${styles["chat-bottom--bottom--mobile"]}`}>
                    <div className={styles["panel-input--mobile"]}>
                        <div className={`${styles["prompt-editor-container--bottom"]}`}>
                            {promptEditor}
                        </div>
                        <div className={styles['input-panel-right--mobile']}>
                            <div className={styles["button-panel"]}>
                                <div
                                    className={`fa-icon -larger  ${loading ? "-gray-with-wobble" : "-blue"} -larger-x`}
                                    title="Send [CTRL + ENTER]"
                                    onClick={(event) => handleSend(event)}
                                    ref={sendButtonRef}
                                >
                                    {loading ? <TbFishBone/> : <FaArrowRight/>}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>)}


            {!isMobile && chatLayout === "bottom" && (
                <div className={`${styles["chat-bottom"]} ${styles["chat-bottom--bottom"]}`}>
                    <div className={`${styles["panel-input"]} ${styles["prompt-active"]}`}>
                        <div className={styles["input-panel-left-container"]}>
                            {codeEditorButton}
                        </div>
                        <div className={`${styles["prompt-editor-container--bottom"]}`}>
                            {promptEditor}
                        </div>
                        <div className={getLayoutSensitiveClassName("input-panel-right")}>
                            <div className={styles["button-panel"]}>
                                <div
                                    className={`fa-icon -larger  ${loading ? "-gray-with-wobble" : "-blue"} -larger-x`}
                                    title="Send [CTRL + ENTER]"
                                    onClick={(event) => handleSend(event)}
                                    ref={sendButtonRef}
                                >
                                    {loading ? <TbFishBone/> : <FaArrowRight/>}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>)}

            {!isMobile && chatLayout === "side" && (
                <div
                    className={`${styles["chat-bottom"]} ${styles["chat-bottom--side"]} ${styles["-flex_" + viewSize]}`}>
                    <div
                        className={`${styles["panel-input"]} ${styles["panel-input--side"]}  ${styles["prompt-active"]}`}>
                        <div
                            className={`${styles["prompt-editor-container"]} ${styles["prompt-editor-container--side"]}`}>
                            {viewSize > 0 && promptEditor}
                            {viewSize === 0 && <div className={styles["prompt-hidden"]}
                                                    onClick={() => {
                                                        const newSize = undoViewSize;
                                                        setViewSize(newSize);
                                                        localStorage.setItem('viewSize', ""+newSize);
                                                    }}
                                                    title={"click to expand"}
                            >
                            </div>}
                        </div>
                    </div>
                    <div className={styles["panel-prompt-side"]}>
                        {viewSize > 0 && <div className={styles["panel-prompt-side-left"]}>
                            {codeEditorButton}
                            {viewSize< 4 && switchViewSizeLeftButton}
                            {viewSize> 1 && switchViewSizeRightButton}
                            {switchViewSizeRightMostButton}
                            {/* {undoInput && undoButton} */}
                            {/* {translateButton} */}
                            {/* {improvePromptButton} */}
                        </div>}
                        {viewSize > 0 && <div className={styles["panel-prompt-side-right"]}>
                            <div
                                className={`fa-icon ${loading ? "-gray-with-wobble" : "-blue"} -larger-x`}
                                onClick={(event) => handleSend(event)}
                                ref={sendButtonRef}
                                title="Send  [CTRL + Enter]"
                            >
                                {loading ? <TbFishBone/> : <FaArrowRight/>}
                            </div>
                        </div>}
                    </div>
                </div>)}

            <input
                type="file"
                style={{display: 'none'}}
                ref={fileInputRefNew}
                onChange={handleFileChangeNew}
                multiple
            />

        </>
    )

    const [systemInContextMessageListModalClickPosition, setSystemInContextMessageListModalClickPosition] = useState(null);
    const systemInContextMessageListModal = !!systemInContextMessageListModalClickPosition && (
        <ContextModal
            clickPosition={systemInContextMessageListModalClickPosition}
            handleClose={() => setSystemInContextMessageListModalClickPosition(null)} closeLabel={"Close"}>

            <div className={styles["modal-container"]}>
                <div className={`${styles["title-with-icon"]} ${styles["modal-header"]}`}>
                    <div className="fa-icon"
                         onClick={() => {
                             handleAddEmptySystemMessage();
                             setSystemInContextMessageListModalClickPosition(null);
                         }}
                         title={"Add empty system message"}
                    >
                        <FaPlus/>
                    </div>
                    <div className="fa-icon"
                         onClick={() => {
                             if( messages.filter(m=> !Array.isArray(m) && !m.entry_id).length > 0)
                             {
                                 if (!window.confirm("Your draft context will be lost. Do you want to continue?")) {
                                     return;
                                 }
                             }
                             navigate('/system_message')
                         }}
                         title={"Edit your system messages"}
                    >
                        <FaEdit/>
                    </div>
                </div>
                <div className={styles["scroll-list-outside-window"]}>
                    <div className={styles["scroll-list-inner-container"]}>
                        {systemMessages.map((option, index) => (
                            <div className={"selection-list-item"} key={index} onClick={() => {
                                handleSelectSystemMessage(index);
                                setSystemInContextMessageListModalClickPosition(null);
                            }}>
                                <div className={styles['modal-list-title']}>{option.title}</div>
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </ContextModal>)

    const [contextListModalClickPosition, setContextListModalClickPosition] = useState(null);
    const contextListModal = !!contextListModalClickPosition && (
        <ContextModal
            clickPosition = {contextListModalClickPosition}
            handleClose={() => setContextListModalClickPosition(null)} closeLabel={"Close"}>

            <div className={styles["modal-content-container"]}>
                <div className={styles["title-with-icon"]}>
                    <div className="fa-icon"
                         onClick={() => {
                             handleAddEmptyMessage();
                             setContextListModalClickPosition(null);
                         }}
                         title={"Add empty context"}
                    >
                        <FaPlus/>
                    </div>
                    <div className="fa-icon"
                         onClick={() => {
                             if (messages.filter(m => !Array.isArray(m) && !m.entry_id).length > 0)
                             {
                                 if (!window.confirm("Your draft context will be lost. Do you want to continue?")) {
                                     return;
                                 }
                             }
                             navigate('/context_artifact')
                         }}
                         title={"Edit your predefine context"}
                    >
                        <FaEdit/>
                    </div>
                </div>
                <div className={styles["modal-list-container-scroll"]}>
                    {contextSnippets.map((option, index) => (
                        <div className={"selection-list-item"} key={index} onClick={async () => {
                            await handleSelectSnippet(index);
                            setContextListModalClickPosition(null);
                        }}>
                            <div className={styles['modal-list-title']}>{option.title}</div>

                            {/*<div className={`${styles['modal-list-content']} code-view`}>{option.content}</div>*/}
                        </div>
                    ))}
                </div>
            </div>
        </ContextModal>
    )

    const handleSaveOrUpdateMessage = async (index, title) => {
        const m = messages[index]
        let response = null
        const role = m.role
        try {
            setLoading(true);
            if (m.role === "system") {
                if (m.preset_id) {
                    response = await api.put(`/api/system_messages/${m.preset_id}`,
                        {content: m.content}   //TDOO: Testar!
                    );
                } else {
                    response = await api.post('/api/system_messages',
                        {content: m.content, title: title, project: currentProject.id}
                    );
                }
            } else { //user
                if (m.preset_id) {
                    response = await api.put(`/api/context_artifacts/${m.preset_id}`,
                        {content: m.content}
                    );
                } else {
                    response = await api.post('/api/context_artifacts',
                        {content: m.content, title: title, project: currentProject.id}
                    );
                }
            }
            const newMessages = [...messages]
            if (!m.preset_id && response?.data?.id) {
                newMessages[index].preset_id = response?.data?.id;
            }
            newMessages[index].modified = false;
            setMessages(newMessages);

            if (role === "system") {
                await loadSystemMessages()
            } else {
                await loadSnippets()
            }
        } finally {
            setLoading(false);
        }
    }

    const [saveModifiedMessage,setSaveModifiedMessage] = useState(null);
    const [editMessageTitle,setEditMessageTitle] = useState(null);

    const modifyModal = !!saveModifiedMessage && (
        <ContextModal
            clickPosition = {saveModifiedMessage.pos}
            handleClose={() => setSaveModifiedMessage(null)} closeLabel={"Close"}>
            <div className={styles["modal-content-container"]}>
                <div className={styles["modal-content-container-header"]}></div>
                <div>Name:</div>
                <input type={"text"}
                       autoFocus
                       className = {"input"}
                       value={editMessageTitle}
                       onChange={e => setEditMessageTitle(e.target.value)}/>
                <button
                    className={"button"}
                    disabled={!editMessageTitle}
                    onClick={async () => {
                        await handleSaveOrUpdateMessage(saveModifiedMessage.index, editMessageTitle);
                        setSaveModifiedMessage(null);
                    }}
                >Save
                </button>
            </div>
        </ContextModal>
    )

    const alternativeRetryModal = !!alternativeRetryParameters && (
        <ContextModal
            clickPosition={alternativeRetryParameters.pos}
            handleClose={() => setAlternativeRetryParameters(null)}
            nonblocking={true}
            closeLabel={"Close"}>
            <div className={styles["alternative-retry-container"]}>
                <div className={styles["alternative-retry-panel-model-selection"]}>
                    <div className={styles["alternative-retry-panel-title-panel"]}>
                        Model: <select value={alternativeRetryParameters?.model}
                                         onChange={(e) => {
                                             setAlternativeRetryParameters(prev => { return {
                                                 ...prev, model: e.target.value}});
                                         }}
                        >
                            {modelListFirstEmpty.map((m, idx) => (
                                <option key={idx} value={m.name}>{m.name}</option>
                            ))}
                        </select>
                    </div>
                </div>
                <div className={styles["alternative-retry-panel"]}>
                    <div className={`fa-icon -larger ${loading?"-gray-with-wobble":"-blue"}`}
                         onClick={async () => {
                             await handleSubmitAlternativeRetry();
                         }}>
                        {loading? <TbFishBone/>: <FaArrowRight/>}
                    </div>
                </div>
            </div>
        </ContextModal>
    )

    const handleClickSysMessage= (e) => {
        console.log( "handleClickSysMessage: ", onTop, showOnTop, (messages || []).length);
        if (onTop) {
            dispatch(setShowOnTop(showOnTop===1?0:1))
        } else {
            const rect = e.target.getBoundingClientRect();
            setSystemInContextMessageListModalClickPosition({top: rect.top, left: rect.left})
        }
    }

    const handleClickContext = (e) => {
        if (onTop) {
            dispatch(setShowOnTop(showOnTop===2?0:2))
        } else {
            const rect = e.target.getBoundingClientRect();
            setContextListModalClickPosition({top: rect.top, left: rect.left})
        }
    }
    const handleClickHistory = (e) => {
        if (onTop) {
            dispatch(setShowOnTop(showOnTop===3?0:3))
        } else {
            const rect = e.target.getBoundingClientRect();
            setHistoryListModalClickPosition({top: rect.top, left: rect.left})
        }
    }

    const predefinedContentToolbar = (
        <div className={styles["predefined-content-toolbar"]}>
            {/* <div className={`fa-icon ${(onTop && showOnTop === 1) && "-color-blue"} -larger`}
                 onClick={handleClickSysMessage}
            >
                <FaDisplay title="Select, add or edit a predefined system message"/>
            </div>
            <div className={`fa-icon ${(onTop && showOnTop === 2) && "-color-blue"} -larger`}
                 onClick={handleClickContext}
                 title="Select, add or edit a predefined system message"
            >
                <FaFileAlt/>
            </div> */}
            {/* <div className={"fa-icon -larger"}
                 onClick={triggerFileInputNew}
                 title="Attach any file  (use is model dependent!)"
            >
                <TbFileSpark />
            </div> */}
            {/* <div className={"fa-icon -larger"}
                 onClick={handleClickHistory}
                 title="Last prompts"
            >
                <TbHistory  />
            </div> */}
            {/* <div className={"fa-icon -larger"}
                 onClick={(e) => {
                     handleAddEmptyMessage();
                 }}
                 title="Add new context area"
            >
                <FaPlus/>
            </div> */}
        </div>
    )

    const initialOptions = (<div className={styles["chat-intro"]}>
        <div className={styles["intro-box"]}>
            {isOwner && predefinedContentToolbar}
        </div>
        {showOnTop === 0 && <div className={styles["intro-box"]}>
            <div className={styles["chat-intro-name"]}>
            </div>
        </div>}
        {showOnTop === 1 && !!systemMessages && systemMessages.length > 0 &&
            <div className={styles["ontop-sys-message"]}>
                {systemMessages.map((option, index) => (
                    <div className={`selection-list-item ${styles["on-top-row"]}`} key={index}>
                        <div className={styles['modal-list-title']}
                             title = {option.content}
                             onClick={() => {
                                 handleSelectSystemMessage(index);
                             }}
                        >{option.title}</div>
                        <div
                            onClick={() => handleTouchSystemMessage(index)}
                            className="fa-icon -smaller"
                            title="move to top"
                        >
                            <LuArrowUpToLine/>
                        </div>
                        <div
                            onClick={() => handleDeleteSystemMessage(index)}
                            className="fa-icon -smaller"
                            title="delete"
                        >
                            <FaTrash/>
                        </div>
                    </div>
                ))}
            </div>}
        {showOnTop === 2 && !!contextSnippets && contextSnippets.length > 0 &&
            <div className={styles["ontop-context-snippet"]}>
                {contextSnippets.map((option, index) => (
                    <div className={`selection-list-item ${styles["on-top-row"]}`} key={index}>
                        <div className={styles['modal-list-title']}
                             title = {option.content}
                             onClick={async () => {
                                 await handleSelectSnippet(index);
                             }}
                        >{option.title}</div>
                        <div
                            onClick={() => handleTouchSnippet(index)}
                            className="fa-icon -smaller"
                            title="move to top"
                        >
                            <LuArrowUpToLine/>
                        </div>
                        <div
                            onClick={() => handleDeleteSnippet(index)}
                            className="fa-icon -smaller"
                            title="delete"
                        >
                            <FaTrash/>
                        </div>

                    </div>
                ))}
            </div>}
        {showOnTop === 3 && (lastPrompts || []).length > 0 &&
            <div className={styles["ontop-context-snippet"]}>
                {lastPrompts.map((option, index) => (
                    <div className={`selection-list-item ${styles["on-top-row"]}`} key={index}>
                        <div className={styles['modal-list-title']}
                             title = {option.content}
                             onClick={async () => {
                                 await handleSelectLastPrompt(index);
                             }}
                        >{option.title}</div>
                    </div>
                ))}
            </div>}
    </div>);

    const sanitizeFilename = (name) => {
        return name.replace(/[/\\?%*:|"<>]/g, '-');
    }

    const handleDeleteChat= async () => {
        if (!chatId) return;
        if (window.confirm(`Delete current chat?`)) {
            try {
                setLoading(true);
                await api.delete(`/api/chats/${chatId}`);
                const r = await api.get(`/api/chats/get-new`,);
                await dispatch(setCurrentChatId(r.data?.chat_id))
                navigate(`/chat/${r.data?.chat_id}`)
            } finally {
                setLoading(false);
            }
        }
    }

    const downloadChat = (text, filename) => {
        if (!messages) return;

        // flatten
        const flatten_messages = [];
        for (let m of messages) {
            for (let entry of m) {
                flatten_messages.push(entry);
            }
        }
        text = flatten_messages.map(m => `${m.role}${m.role==="assistant"?"("+m.meta?.model+")":""}: ${m.content}`).join('\n\n');

        const blob = new Blob([text], { type: 'text/plain' });

        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = "Imagery - "+ sanitizeFilename(title || "Chat")+ ".txt";

        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    };

    const toggleBookmark = () => {
        api.put(`/api/bookmarks/${chatId}/toggle`).then(response => {
            setChatInfo(prevState => ({...prevState, is_bookmarked: response.data}));
        })
        .catch((error)=> { /*error handled in apiService*/})
    }
    const togglePublic = () => {
        if (!chatInfo?.public_at) {
            if (!window.confirm("Making this chat public will display it on teammates' home screens in anonymous way for a few days. You can undo this change at any time. Confirm?")) {
                return;
            }
        }

        api.put(`/api/chats/${chatId}/public`).then(response => {
            setChatInfo(prevState => ({...prevState, public_at: response.data}));
        })
        .catch((error)=> { /*error handled in apiService*/})
    }

    const divMeta = chatInfo?.created_at && (<div className={styles["chat-meta"]}>
        <div>Estimated Cost(U$): <span>{chatInfo?.estimate_total_cost}</span>, Tokens Input: {chatInfo?.total_input_tokens}, Output: <span>{chatInfo?.total_output_tokens}</span></div>
        </div>
    )

    if (projectMismatch) {
        return (<div className={"font-mono"}>Project mismatch.</div>);
    }

    const editMessageInlineOnBlur = (index,content)=> {
        setMessages ((prevMessages ) => {
            let newMessages = [...prevMessages ];
            newMessages[index].content = content
            newMessages[index].modified = true
            return newMessages;
        });
    }

    const moveMessageUp = (index) => {
        setMessages ((prevMessages ) => {
            let temp = prevMessages[index-1];
            let newMessages = [...prevMessages ];
            newMessages[index-1] = messages[index];
            newMessages[index] = temp;
            return newMessages;
        });
    }

    // if (config.is_dev) printRender();

    return (
        <div className={getLayoutSensitiveClassName("chat-top-container")}>
            {/* <div>Chat.js here!</div> */}
            <DragAndDrop onFileDrop={handleDropFilesNew}/>
            <div className={getLayoutSensitiveClassName("chat-top")}>
                <div className={styles["chat-top-inner-scroll"]}>
                    {messages.length <= 0 && initialOptions}
                    {messages.length > 0 && (
                        <div className={`code-view-in-chat ${styles["chat-conversation-top"]} ${(useMulti && showMultiColumn)? styles['with-multi']:null} `}>
                            {(chatId && !temporaryChat) && <div className={styles["chat-thread-header"]}>
                                <div>
                                    <div className={"font-mono"}>{createdAt}</div>
                                    <Title>{title}</Title>
                                </div>
                                <div className={styles["chat-thread-header-buttons"]}>
                                    {/* <div onClick={() => toggleBookmark()}
                                         className="fa-icon" title={"Favorite"}>
                                        {chatInfo?.is_bookmarked ? (
                                            <FaBookmark className={"-main-color-alternative"}/>
                                        ) : (
                                            <FaRegBookmark/>
                                        )}
                                    </div>
                                    {isOwner && <div onClick={() => setShowSharedModal(true)}
                                         className="fa-icon" title={"share"}>
                                        <FaShareAlt/>
                                    </div>} */}
                                    {/* <div onClick={() => downloadChat()}
                                         className="fa-icon" title={"download"}>
                                        <FaDownload/>
                                    </div> */}
                                    {/* {isOwner && <div onClick={() => handleDeleteChat()}
                                                     className="fa-icon -delete" title={"delete chat"}>
                                        <FaTrash/>
                                    </div>} */}
                                </div>
                            </div>}
                            {divMeta}
                            {formattedMessages.map((message, index) => (
                                <MessageCard
                                    key={message.entry_id ?? `tmp-${index}`}
                                    // key={index}
                                    {...{ /* adjust to the parameters expected by MessageBlock */
                                        message,
                                        index,
                                        isOwner,
                                        showMultiColumn,
                                        is_last : index===messages.length-1,
                                        is_previous_draft: index>0 && !messages[index-1].entry_id,
                                        is_alternatives_full: Array.isArray(message) && message.length>= MAX_ALTERNATIVES+1,
                                        focusEntryIndex,
                                        setFocusEntryIndex,
                                        lastMessageRef,
                                        handleDeletePresetEntry,
                                        handleSwitchRole,
                                        handleDeleteEntry,
                                        handleCopyContent,
                                        handleAlternativeRetry,
                                        // handleResubmitSelected,
                                        handleSaveOrUpdateMessage,
                                        setSaveModifiedMessage,
                                        setEditMessageTitle,
                                        editMessageInlineOnBlur,
                                        moveMessageUp,
                                        handleMakeAlternativeMain,
                                        handleBranchInNewChat
                                    }}
                                    />
                            ))}
                            {isOwner && predefinedContentToolbar}
                            <div className={styles["zero-height"]} ref={chatEndRef}/>
                        </div>
                    )}
                    {isMobile && (<>
                            <div className={styles["chat-fullscreen-panel"]}>
                                {messages.length > 0 &&
                                    <div className={`fa-icon -larger-xx`} onClick={() => moveScrollToEnd()}>
                                        <FaArrowDown/>
                                    </div>}
                                {messages.length > 0 && <div className={"fa-icon -larger-xx"}
                                     title={isDisableFormat ? "Enable format" : "Disable format"}
                                     onClick={() => dispatch(setDisableFromat(!isDisableFormat))}>
                                    {isDisableFormat ? <MdCode/> : <MdCodeOff/>}
                                </div>}
                            </div>
                        </>
                    )}

                </div>
            </div>

            {/* {isOwner && chatInputPanel} */}
            {/* {sharedModal} */}
            {/* {candidateInputDiv} */}
            {loading && <Busy/>}
            {/* {systemInContextMessageListModal} */}
            {/* {contextListModal} */}
            {/* {modifyModal} */}
            {/*{resubmitModal}*/}
            {/* {alternativeRetryModal} */}
        </div>
    );
}

export default Chat;
