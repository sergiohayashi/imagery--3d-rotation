import styles from "./Chat.module.css"
import styles2 from "./MessageCard.module.css"
import React, {useContext} from "react";
import {AppContext} from "../../redux/AppContext";
import {ThemeContext} from "../../redux/ThemeContext";
import Logo from "../Logo/Logo";
import FullMarkdown from "../FullMarkdown/FullMarkdown";
import {FileMessage, FileMessageForOutput} from "./FileMessage";
import {setInfoMessage} from "../../redux/actions";
import {FaArrowUp, FaInfo, FaUser} from "react-icons/fa";
import {FaCopy, FaDisplay, FaFloppyDisk, FaPlus, FaTrash} from "react-icons/fa6";
import {TbArrowFork} from "react-icons/tb";
import {TiUserAdd} from "react-icons/ti";
import {IoMdAdd} from "react-icons/io";

const MessageBlock = (
    {
        message,
        index
    }) => {

    const { state, dispatch } = useContext(AppContext);
    const { theme } = useContext(ThemeContext);
    const { isMobile } = state;

    return (
        <div key={index}
             className={`${styles[message.role]} ${styles["role-div"]}`}
        >
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
                    {message.role === "assistant" && <div className={styles["model-name-sub"]}>{message.meta?.model}</div>}
                    {message.role === "assistant" ? (
                        <div className={styles["markdown-parent"]}>
                            <FullMarkdown content={message.content}/>
                        </div>
                    ) : (
                        message.content
                    )}
                    {message.image_url && (
                        <div>
                            <a href={message.image_url} target="_blank" rel="noopener noreferrer">
                                <img className={styles["image-in-thread"]} src={message.image_url}/>
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
            </div>
        </div>);
}


const MessageCardForShared = (params) =>  {
    const {message} = params;
    if (Array.isArray(message)) {
        if (message.length===1) {
            return (<MessageBlock
                {...params}
                message={message[0]}
            />);
        } else {
            return (
                <div className={`${styles2["chat-entry-multi-container"]}`}>
                    {message.map((m, index) => <div className={styles2['chat-entry-multi-column']}>
                    <MessageBlock
                        {...params}
                        message={m}
                    />
                    </div>)}
                </div>)
        }
    } else {
        return (
            <MessageBlock
                {...params}
            />);
    }
}

export default MessageCardForShared;

