import styles from "./Chat.module.css"
import styles2 from "./MessageCard.module.css"
import {memo, useContext} from "react";
import {AppContext} from "../../redux/AppContext";
import {ThemeContext} from "../../redux/ThemeContext";
import Logo from "../Logo/Logo";
import FullMarkdown from "../FullMarkdown/FullMarkdown";
import {FileMessage, FileMessageForOutput, handleLocalFile} from "./FileMessage";
import {setInfoMessage} from "../../redux/actions";
import {FaArrowUp, FaInfo, FaUser} from "react-icons/fa";
import {FaCopy, FaDisplay, FaFloppyDisk, FaPlus, FaTrash} from "react-icons/fa6";
import {TbArrowFork} from "react-icons/tb";
import {TiUserAdd} from "react-icons/ti";
import {IoMdAdd} from "react-icons/io";
import {TfiShiftLeft} from "react-icons/tfi";
import {LuGitBranchPlus} from "react-icons/lu";


const toElapsedStr = (d) => {
    if (d == null) return '';
    return d.toFixed(1) + 's';
}
const toDollarCost = (v) => {
    if (v == null) return '';
    return 'U$'+ v.toFixed(3);
}

const MessageBlock = (
    {
        message,
        index,
        isOwner,
        is_last = false,
        is_previous_draft,
        is_alternatives_full = false,
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
        handleBranchInNewChat,
        is_main_thread = true
    }) => {

    const { state, dispatch } = useContext(AppContext);
    const { theme } = useContext(ThemeContext);
    const { isMobile, isDisableFormat, temporaryChat } = state;

    return (
        <div key={index}
             className={`${styles[message.role]} 
             ${styles["role-div"]} ${(message.entry_id==null && !temporaryChat)?styles["chat-entry-preset"]:''}`}
             onPointerEnter={()=> setFocusEntryIndex(index)}
             onPointerLeave={()=> setFocusEntryIndex(null)}
        >
            {/*{windowFirstEntryId && windowFirstEntryId === message.entry_id &&*/}
            {/*    <hr className={styles["chat-conversation-start-window"]}/>*/}
            {/*}*/}
            {is_last &&
                <div className={styles["zero-height"]} ref={lastMessageRef}/>}

            <div className={styles["icon-role"]}>
                {message.role === "system" && <img
                    src={theme === "dark" ? "/icons8-system-50--dark.png" : "/icons8-system-50--light.png"}
                />}
                {message.role === "user" && !isMobile && <img
                    src={theme === "dark" ? "/icons8-user-60-dark.png" : "/icons8-user-60-light.png"}
                />}
                {message.role === "assistant" && <Logo company={message.meta?.company}/>}
            </div>

            <div className={styles["message-entry-line"]}>
                <div className={`markdown ${styles["message-entry-message"]}`}>
                    {message.role === "assistant" &&
                        <div className={styles["model-name-sub"]}>
                            <div className={"bold"}> {message.meta?.model}</div>
                            <div>{toElapsedStr(message.meta?.elapsed_in_sec)}</div>
                            <div>{toDollarCost(message.meta?.estimate_price)}</div>
                        </div>}
                    {message.role === "assistant" && !isDisableFormat? (<>
                            {message.formatted ||
                                <div className={styles["markdown-parent"]}><FullMarkdown
                                    content={message.content}/></div>}
                        </>
                    ) : (
                        (message.entry_id || message?.image_url || message?.file_url)?
                            <div className={"font-mono"}>
                                {message.content}
                            </div> :
                            (
                                <div
                                    className={"font-mono"}
                                    contentEditable
                                    data-placeholder="Enter text here..."
                                    suppressContentEditableWarning={true}
                                    onBlur={(event)=> editMessageInlineOnBlur(index, event.target.innerText)}>
                                    {message.content}
                                </div>
                            )
                    )}
                    {message.image_url && (
                        <div>
                            <a href={handleLocalFile(message.image_url)} target="_blank"
                               rel="noopener noreferrer">
                                <img className={styles["image-in-thread"]}
                                     src={handleLocalFile(message.image_url)}/>
                            </a>
                        </div>
                    )}
                    <FileMessage message={message} />
                    {(message.output || []).map((m, index) => <>
                        <FileMessageForOutput output={m}/>
                    </>)}
                    {message.meta?.grounding_list &&
                        <div className={styles['citation-div']}>
                            {message.meta?.grounding_list.map((m, index)=> <div>
                                <a href={m.uri} target="_blank">{m.title}</a>
                            </div>)}
                        </div>
                    }
                </div>

                <div
                    className={`${styles["message-entry-commands"]} ${index !== focusEntryIndex && !isMobile && styles["opaque-invisible"]}`}>
                    {!message.entry_id && is_previous_draft && (
                        <div onClick={() => moveMessageUp(index)}
                             className="fa-icon" title={"move up"}>
                            <FaArrowUp/>
                        </div>
                    )}
                    {!message.entry_id && (
                        <div onClick={() => handleDeletePresetEntry(index)}
                             className="fa-icon -smaller" title={"delete chat entry"}>
                            <FaTrash/>
                        </div>
                    )}
                    {!message.entry_id && message.role === "system" && (
                        <div onClick={() => handleSwitchRole(index, "user")}
                             className="fa-icon -smaller" title={"switch to user message"}>
                            <FaUser/>
                        </div>
                    )}
                    {!message.entry_id && message.role === "user" && (
                        <div onClick={() => handleSwitchRole(index, "system")}
                             className="fa-icon -smaller" title={"switch to system message"}>
                            <FaDisplay/>
                        </div>
                    )}
                    {/* {message.entry_id && isOwner && (
                        <div onClick={() => handleDeleteEntry(message.entry_id)}
                             className="fa-icon -smaller" title={"delete chat entry"}>
                            <FaTrash/>
                        </div>
                    )} */}
                    {!!message.content && <div onClick={() => handleCopyContent(message.content)}
                                               className="fa-icon -smaller" title={"copy chat entry"}>
                        <FaCopy/>
                    </div>}
                    {/*{message.entry_id && message.role === "user" && (*/}
                    {/*    <div onClick={(event) => {*/}
                    {/*        const rect = event.target.getBoundingClientRect();*/}

                    {/*        handleResubmitSelected(*/}
                    {/*            {top: rect.bottom, left: rect.right},*/}
                    {/*            index,*/}
                    {/*            message.content*/}
                    {/*        )*/}
                    {/*    }}*/}
                    {/*         className="fa-icon -smaller" title={"branch from here"}>*/}
                    {/*        <TbArrowFork />*/}
                    {/*    </div>*/}
                    {/*)}*/}
                    {!message.entry_id && message.modified && !message.image_url && (
                        <div onClick={async (e) => {
                            if (message.preset_id) {
                                await handleSaveOrUpdateMessage(index, null)
                            } else {
                                const rect = e.target.getBoundingClientRect();
                                setEditMessageTitle('');
                                setSaveModifiedMessage({
                                    pos: {top: rect.top, left: rect.left},
                                    index
                                })
                            }
                        }}
                             className="fa-icon -smaller" title={"Save the edited context for future use."}>
                            <FaFloppyDisk/>
                        </div>
                    )}
                    {/* meta   */}
                    {!!message.meta && (
                        <div
                            title={JSON.stringify(message.meta)}
                            onClick={()=>dispatch(setInfoMessage(JSON.stringify(message.meta)))}
                            className="fa-icon -smaller"
                        >
                            <FaInfo  />
                        </div>
                    )}
                    {/* {!is_alternatives_full && message.entry_id && isOwner && message.role === "assistant" && (
                        <div onClick={(event) => {
                                const rect = event.target.getBoundingClientRect();

                                handleAlternativeRetry(
                                    {top: rect.bottom, left: rect.right},
                                    index,
                                    message.entry_id
                                )
                            }}
                            className="fa-icon -smaller" title={"retry with another alternative model"}>
                            <FaPlus   />
                        </div>
                    )} */}
                    {/* {!is_main_thread && message.entry_id && isOwner && message.role === "assistant" && (
                        <div onClick={(event) => {
                            handleMakeAlternativeMain(message.entry_id)
                        }}
                             className="fa-icon -smaller" title={"make this alternative main thread"}>
                            <TfiShiftLeft    />
                        </div>
                    )} */}
                    {/* {message.entry_id && isOwner && message.role === "assistant" && (
                        <div onClick={(event) => {
                            handleBranchInNewChat(message.entry_id)
                        }}
                             className="fa-icon -smaller" title={"branch in new chat"}>
                            <LuGitBranchPlus     />
                        </div>
                    )} */}


                </div>
            </div>
        </div>);
}


const MessageCard = (params) =>  {
    const {message, showMultiColumn} = params;
    if (Array.isArray(message)) {
        if (message.length===1) {
            return (
                <div className={styles2['chat-entry-one-container']}>
                    <MessageBlock
                    {...params}
                    message={message[0]}
                /></div>);
        } else {
            return (
                <div className={`${styles2["chat-entry-multi-container"]} ${showMultiColumn?undefined:styles2["single-column"]}`}>
                    {message.map((m, index) => <div
                        key={index}
                        className={styles2['chat-entry-multi-column']}>
                    <MessageBlock
                        {...params}
                        message={m}
                        is_main_thread = {index=== 0}
                    />
                    </div>)}
                </div>)
        }
    } else {
        return (
            <div className={styles2['chat-entry-one-container']}>
            <MessageBlock
                {...params}
            /></div>
                );
    }
}

export default memo(MessageCard);

