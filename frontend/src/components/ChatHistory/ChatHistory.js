import React, {useContext, useEffect, useState, useRef} from "react";
import styles from "./ChatHistory.module.css"
import {AppContext} from "../../redux/AppContext";
import {ThemeContext} from "../../redux/ThemeContext";
import {setCurrentChatId} from "../../redux/actions";
import {useNavigate} from "react-router-dom";
import ContextModal from "../ContextModal/ContextModal";
import Busy from "../Busy/Busy";
import { useApi } from "../../hooks/useApi"
import {FaBookmark, FaCopy, FaDisplay, FaDownload, FaRegBookmark, FaTrash, FaXmark} from "react-icons/fa6";
import {FaEdit, FaRobot, FaSearch, FaUser} from "react-icons/fa";
import {TfiReload} from "react-icons/tfi";
import {PiExportFill} from "react-icons/pi";

// Debounce function
let debounceTimer;
const debounce = (func, delay) => {
    return function() {
        const context = this;
        const args = arguments;
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => func.apply(context, args), delay);
    }
}

function ChatHistory() {
    const [loading, setLoading] = useState(false);
    const [chatHistory, setChatHistory] = useState([]);
    const [chatHistoryIsAll, setChatHistoryIsAll] = useState(true);
    const { state, dispatch } = useContext(AppContext);
    const { currentProject, currentChatId, forceRefreshHistory } = state;
    const [isRenameModalOpen, setRenameModalOpen] = useState(false);
    const [isExportModalOpen, setExportModalOpen] = useState(false);
    const [selectedChatToAction, setSelectedChatToAction] = useState(null);
    const [chatNewTitle, setChatNewTitle] = useState('');
    const { theme } = useContext(ThemeContext);
    const navigate = useNavigate();
    const [lastId, setLastId] = useState(null);
    const [forceReloadWithDelay, setForceReloadWithDelay] = useState(null);
    const [isBookmarked, setBookmarked] = useState(false);
    const [chatSearchText, setChatSearchText] = useState('');
    const scrollDivRef = useRef(null);
    // const [isDuplicateModalOpen, setDuplicateModalOpen] = useState(false);
    // const [duplicateParameters, setDuplicateParameters] = useState([]);

    const currentProjectRef = useRef(currentProject);
    const chatIdRef = useRef(currentChatId);

    useEffect(() => {
        currentProjectRef.current = currentProject;
        chatIdRef.current = currentChatId;
    }, [currentProject, currentChatId]);

    const api = useApi();

    useEffect(() => {
        if (currentProject) {
            loadChatHistory();

        }
    }, [currentProject]);

    useEffect(() => {
        if (currentChatId && !chatHistory.some(d=> d.id === currentChatId )) {
            loadChatHistory();
        }
    }, [currentChatId]);

    useEffect(()=> {
        if (forceReloadWithDelay) {
            setTimeout(() => {
                loadChatHistory();
            }, 10000)
        }
    },[forceReloadWithDelay])

    useEffect(()=> {
        if (forceRefreshHistory) {
            setTimeout(() => {
                loadChatHistory();
            }, 5000)
        }
    },[forceRefreshHistory])




    const loadChatHistory = (_isBookmarked = isBookmarked, _query = chatSearchText) => {
        // const loadingProjectId =currentProject.id

        api.get("/api/chats/search/titles", {
            params: {
                project_id: currentProject?.id,
                selected_chat_id: chatIdRef?.current,
                is_bookmarked: _isBookmarked,
                q: _query,
                // file_context_id: currentFileContext?.id,
            }
        })
            .then(response => {
                if (response.data.project_id !== currentProjectRef.current.id) {
                    console.log( 'oudated project id. discard', response.data.project_id, currentProjectRef.current.id)
                    return;
                }
                setChatHistoryIsAll(response.data?.is_all);
                const dataList = response.data?.list || [];
                setChatHistory(dataList);
                if (dataList.length > 0) {
                    setLastId(dataList[dataList.length - 1].id);
                    const current = dataList.find(chat => chat.id == currentChatId);
                    if (current?.title == "(no name)" || current?.title?.startsWith("Cont.")) {
                        setForceReloadWithDelay(currentChatId)
                    } else {
                    }
                }
            })
            .catch((error)=> { /*error handled in apiService*/});
    }
    const loadChatHistoryMore = () => {
        if (chatHistoryIsAll) return;
        api.get("/api/chats/search/titles", {
            params: {
                project_id: currentProject.id,
                // selected_chat_id: chatId,
                last_id: lastId,
                is_bookmarked: isBookmarked,
                q: chatSearchText,
                // file_context_id: currentFileContext?.id,
            }
        })
            .then(response => {
                setChatHistoryIsAll(response.data?.is_all);
                const dataList = response.data?.list || [];
                if (dataList.length > 0) {
                    setChatHistory([...chatHistory, ...dataList]);
                    setLastId(dataList[dataList.length - 1].id);
                }
            })
            .catch((error)=> { /*error handled in apiService*/});
    }

    const handleChatSearch = debounce((_query) => {
        loadChatHistory(isBookmarked, _query);
    }, 500); // 500ms delay

    useEffect(() => {
        const scrollDiv = scrollDivRef.current;
        if (scrollDiv) {
            const handleScroll = () => {
                // Check if we're at the bottom of the div
                if (((scrollDiv.scrollTop + scrollDiv.clientHeight) - scrollDiv.scrollHeight) >=0) {
                    loadChatHistoryMore();
                }
            };

            scrollDiv.addEventListener('scroll', handleScroll);

            // Cleanup function to remove the event listener
            return () => scrollDiv.removeEventListener('scroll', handleScroll);
        }
    }, [loadChatHistory,loadChatHistoryMore]);


    const handleChatHistoryClick = async (e, _chatId) => {
        const openInNewTab = e.ctrlKey || e.metaKey || e.button === 1;
        if (openInNewTab) {
            window.open(`/#/chat/${_chatId}`, '_blank', 'noopener,noreferrer');
        } else {
            await dispatch(setCurrentChatId(_chatId))
            navigate(`/chat/${_chatId}`);
        }
    }


    const handleRename= async (_chatId, newTitle) => {
        await api.put(`/api/chats/${_chatId}/rename`, {
            title: newTitle
        });
        await loadChatHistory()
    }

    // const toggleChatBookmark = async (_chatId) => {
    //     setLoading(true);
    //     try {
    //         await api.put(`/api/bookmarks/${_chatId}/toggle`);
    //         await loadChatHistory()
    //     } finally {
    //         setLoading(false);
    //     }
    // }

    // const handleDeleteChat= async (deleteChatId, title) => {
    //     if (window.confirm(`Delete entire conversation of "${title}"?`)) {
    //         await api.delete(`/api/chats/${deleteChatId}`);
    //         setChatHistory( chatHistory.filter( chat=> chat.id !== deleteChatId));
    //         if (deleteChatId == currentChatId) {
    //             dispatch( setCurrentChatId(null));
    //         }
    //     }
    // }

    // const handleSelectiveDuplicate= async (_chatId, title, clickPosition) => {
    //     setLoading(true);
    //     try {
    //         const result = await api.get(`/api/chats/${_chatId}/entries-selection-list`);
    //         const selectedEntries = result.data.reduce((acc, d) => {
    //             acc[d.entry_id] = true;
    //             return acc;
    //         }, {})
    //         setDuplicateParameters({
    //             entriesList: result.data,
    //             chatId: _chatId,
    //             clickPosition,
    //             selectedEntries,
    //             title
    //         })
    //         setDuplicateModalOpen(true)
    //     } finally {
    //         setLoading(false);
    //     }
    // }

    // const handleDuplicateSelection = (entry_id) => {
    //     setDuplicateParameters((prevState) => ({
    //         ...prevState,
    //         selectedEntries: {
    //             ...prevState.selectedEntries,
    //             [entry_id]: !prevState.selectedEntries[entry_id]
    //         }
    //     }));
    // };

    // async function handleExecSelectiveDuplicate() {
    //     setLoading(true);
    //     try {
    //         const response = await api.post(`/api/chats/${currentChatId}/selective-duplicate`, {
    //             title: duplicateParameters.title,
    //             entries: Object.keys(duplicateParameters.selectedEntries).filter(id => duplicateParameters.selectedEntries[id])
    //         });
    //         setDuplicateModalOpen(false);
    //         await loadChatHistory()
    //         dispatch( setCurrentChatId(response.data));
    //     } finally {
    //         setLoading(false);
    //     }
    // }

    // const duplicateModal = isDuplicateModalOpen && (
    //     <ContextModal
    //         show={isDuplicateModalOpen}
    //         clickPosition={duplicateParameters.clickPosition}
    //         handleClose = {()=> setDuplicateModalOpen(false)}
    //         >
    //         <div className={styles["duplicate-modal-container"]}>
    //             <div  className={styles["duplicate-modal-entries"]}>
    //                 {(duplicateParameters.entriesList || []).map((m, index)=> (
    //                     <div className={`${styles["duplicate-modal-row"]} list-item`}
    //                          onClick={() => handleDuplicateSelection(m.entry_id)}
    //                     >
    //                         <div>
    //                             {!!duplicateParameters.selectedEntries[m.entry_id] && <img src ="/icons8-checked-48.png" alt="selected"/>}
    //                         </div>
    //                         <div className={styles["icon-role"]}>
    //                             {m.role === "system" && <FaDisplay />}
    //                             {m.role === "user" && <FaUser/>}
    //                             {m.role === "assistant" && <FaRobot />}
    //                         </div>
    //                         <div>
    //                             {m.content}
    //                             {m.file_url? "(file)": ''}
    //                             {m.image_url? "(image)": ''}
    //                         </div>
    //
    //                     </div>
    //                 ))}
    //             </div>
    //             <div className={styles["duplicate-modal-panel"]}>
    //                 <div  className={styles["duplicate-modal-panel-title"]}>
    //                     New title: <input type={"text"} value={duplicateParameters.title}
    //                                   onChange = {e => {
    //                                       setDuplicateParameters((prevState) => ({
    //                                           ...prevState,
    //                                           title: e.target.value
    //                                       }));
    //                                   }}/>
    //                 </div>
    //                 <button
    //                     className="button"
    //                     onClick={async () => {
    //                         await handleExecSelectiveDuplicate()
    //                     }}>Duplicate
    //                 </button>
    //             </div>
    //         </div>
    //     </ContextModal>
    // )

    const renameModal = !!isRenameModalOpen && (
        <ContextModal
            show={isRenameModalOpen}
            clickPosition = {isRenameModalOpen}
            handleClose={() => {
                setRenameModalOpen( false);
            }}
        >
            <div className={`${styles["modal-container"]} context-modal-margin`}>
                <input
                    type={"text"}
                    className={"input"}
                    autoFocus
                    value={chatNewTitle}
                    onChange = {e=>setChatNewTitle(e.target.value)}/>
                <button
                    className={"button"}
                    onClick = {async () => {
                        await handleRename(selectedChatToAction.id, chatNewTitle);
                        setRenameModalOpen(null);
                    }}
                >Save</button>
            </div>
        </ContextModal>
    )

    function toggleBookmarked() {
        loadChatHistory( !isBookmarked, chatSearchText);
        setBookmarked((prevState)=> !prevState)
    }

    const divPanel = (
        <div className={styles["panel"]}>
            <div className={styles["search-box"]}>
                <input
                    type={"text"}
                    className={"input"}
                    value={chatSearchText}
                    onChange={e => {
                        setChatSearchText(e.target.value);
                        handleChatSearch(e.target.value);
                    }}/>
                {!chatSearchText && <div className={`fa-icon ${styles["search-box-icon"]}`}
                >
                    <FaSearch/>
                </div>}
                {!!chatSearchText && <div className={`fa-icon ${styles["search-box-icon"]}`}
                                          onClick={() => {
                                              setChatSearchText('');
                                              handleChatSearch('')
                                          }}>
                    <FaXmark/>
                </div>}
            </div>
            <div className={styles["search-box-panel"]}>
                {/* <div onClick={() => toggleBookmarked()}
                     className="fa-icon -small" title={"Favorite"}>
                    {isBookmarked ? (
                        <FaBookmark className={"-main-color"}  title="Bookmarked"/>
                    ) : (
                        <FaRegBookmark title="Not Bookmarked"/>
                    )}
                </div> */}
                <div onClick={() => loadChatHistory()}
                     className="fa-icon -small" title={"refresh"}>
                    <TfiReload title="refresh"/>
                </div>


                {/* <div onClick={(e) => {
                    const rect = e.target.getBoundingClientRect();
                    setExportModalOpen({top: rect.top, left: rect.left})
                }}
                     className="fa-icon -small" title={"download"}>
                    <PiExportFill  title="export"/>
                </div> */}
            </div>

        </div>)


    return (
        <div className={styles["chat-history"]}>
            {/* <div>ChatHistory.js here!</div> */}
            {/*{isMobile && <TopMostNavBar/>}*/}
            {divPanel}
            <div className={styles["chat-history-inner-scroll"]} ref={scrollDivRef}>
                <div className={styles["chat-history-list"]}>
                    <div>chatHistory length: {chatHistory?.length}</div>
                    {chatHistory.map((chat, index) => (
                        <div key={index} className={styles["chat-history-entry"]}>
                            <div
                                onClick={(e) => handleChatHistoryClick(e, chat.id)}
                                className={`${styles["chat-history-title"]} ${currentChatId === chat.id ? styles["is-current"] : ""}  ${chat.isOwner ? "" : styles[theme === "dark" ? "darken" : ""]} `}
                                title={chat.title}
                            >
                                {chat.title}
                                {chat.is_bookmarked && (
                                    <FaBookmark size={12} className={"-main-color"}/>
                                )}
                            </div>
                            {chat.branch_model && <div
                                className={`${styles["chat-history-model"]} ${styles[theme == "dark" ? "darken" : "lighten"]}`}>{chat.branch_model}</div>}
                            {!chat.isOwner && <div
                                className={`${styles["chat-history-owner"]} ${styles[theme == "dark" ? "darken" : "lighten"]}`}>{chat.owner}</div>}
                            {currentChatId === chat.id && (
                                <div className={styles["chat-history-actions"]}>
                                    {/*<div className="fa-icon -smaller" onClick={(e) => {*/}
                                    {/*    const rect = e.target.getBoundingClientRect();*/}
                                    {/*    handleSelectiveDuplicate(chat.id, chat.title, {top: rect.top, left: rect.left});*/}
                                    {/*}}>*/}
                                    {/*    <FaCopy title="Fork"/>*/}
                                    {/*</div>*/}

                                    {/* {chat.isOwner && <div className="fa-icon -smaller" onClick={(e) => {
                                        setSelectedChatToAction(chat);
                                        setChatNewTitle(chat.title);
                                        const rect = e.target.getBoundingClientRect();
                                        setRenameModalOpen({top: rect.top, left: rect.left})
                                    }}>
                                        <FaEdit title="Rename" />
                                    </div>} */}

                                    {/*<div onClick={() => toggleChatBookmark(chat.id)}*/}
                                    {/*     className="fa-icon -smaller" title={"Favorite"}>*/}
                                    {/*    {chat?.is_bookmarked ? (*/}
                                    {/*        <FaBookmark className={"-main-color"} title="Bookmarked" />*/}
                                    {/*    ) : (*/}
                                    {/*        <FaRegBookmark title="Not Bookmarked" />*/}
                                    {/*    )}*/}
                                    {/*</div>*/}

                                    {/*{chat.isOwner && <div className="fa-icon -smaller" onClick={() => {*/}
                                    {/*    handleDeleteChat(chat.id, chat.title)*/}
                                    {/*}}>*/}
                                    {/*    <FaTrash title="Delete" />*/}
                                    {/*</div>}*/}
                                </div>)}
                        </div>
                    ))}
                    {!chatHistoryIsAll && <div className={styles["load-more"]}>
                        <a onClick={() => loadChatHistoryMore()}>load more...</a>
                    </div>}
                </div>
            </div>
            {isRenameModalOpen && renameModal}
            {/*{isDuplicateModalOpen && duplicateModal}*/}
            {loading && <Busy/>}
        </div>
    )

}


export default ChatHistory;
