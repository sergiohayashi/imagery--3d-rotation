import styles from "./PublicChats.module.css"
import React, {useContext, useEffect, useState} from "react";
import {ThemeContext} from "../../redux/ThemeContext";
import { AppContext } from '../../redux/AppContext'; // import AppContext
import {useMsal} from "@azure/msal-react";
import MaxModal from "../MaxModal/MaxModal";
import CodeWithHighlighting from "../CodeWithHighlighting/CodeWithHighlighting";
import FullMarkdown from "../FullMarkdown/FullMarkdown";
import {useApi} from "../../hooks/useApi";
import {SectionTitle, Subtitle, Title} from "../Headings/Heading";
import {ReactComponent as XaiIcon} from "../../icons/grok.svg"
import {FaGlobe} from "react-icons/fa6";
import Logo from "../Logo/Logo";
import {FileMessage} from "./FileMessage";

function PublicChats() {
    const { theme } = useContext(ThemeContext);
    const { state, dispatch } = useContext(AppContext);
    const { isMobile } = state;
    const [publicList, setPublicList] = useState([])
    const [messages, setMessages] = useState(null)
    const [title, setTitle] = useState([])
    const [detailId, setDetailId] = useState(null);

    const api = useApi();

    useEffect(() => {
        const loadPublic = () => {
            api.get('/api/chats/search/public').then(response => {
                setPublicList(response.data);
            })
            .catch((error)=> { /*error handled in apiService*/})
        }
        loadPublic()
    }, [])


    const loadChatThread = (chatId) => {
        api.get(`/api/chats/${chatId}/thread-public`, )
            .then(response => {
                setMessages(response.data.entries);
                setTitle(response.data.title);
                setDetailId (chatId);
            })
            .catch((error) => { /*error handled in apiService*/
            });
    }

   const chatDetailDiv = messages && (
        <MaxModal show={true} handleClose={()=> setMessages(null)}  useMaxFixed={true}>
            <div className={`code-view-in-chat ${styles["chat-container"]}`}>
                {messages.map((message,index) => (
                    <div key={index}
                         className={`${styles[message.role]} 
                         ${styles["role-div"]}`}
                    >
                        <div className={styles["icon-role"]}>
                            {message.role === "system" && <img
                                src={theme === "dark" ? "/icons8-system-50--dark.png" : "/icons8-system-50--light.png"}
                            />}
                            {message.role === "user" && !isMobile && <img
                                src={theme === "dark" ? "/icons8-user-60-dark.png" : "/icons8-user-60-light.png"}
                            />}
                            {message.role === "assistant" && <Logo company={message.meta?.company}/>}
                            {/*message.meta?.company != "XAI" && <img*/}
                            {/*    src={*/}
                            {/*        message.meta?.company === "MISTRAL" ? "/mistral.png" :*/}
                            {/*            (message.meta?.company === "GEMINI" ? "/gemini.png" : (theme === "dark" ? "/icons8-chatgpt-50-dark.png" : "/icons8-chatgpt-50-light.png"))}*/}
                            {/*/>}*/}
                            {/*{message.role === "assistant" && message.meta?.company === "XAI" &&*/}
                            {/*    <div className={"svg-icon"}><XaiIcon/></div>}*/}
                        </div>

                        <div className={styles["message-entry-line"]}>
                            <div className={`markdown ${styles["message-entry-message"]}`}>
                                {message.role === "assistant" &&
                                    <div className={styles["model-name-sub"]}>{message.meta?.model}</div>}

                                {message.role === "assistant" ? (
                                    <div className={styles["markdown-parent"]}>
                                        <FullMarkdown content={message.content}/>
                                    </div>
                                    // <TextWithFormulas text={message.content}/>
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
                            </div>
                        </div>
                    </div>
                ))}
            </div>
        </MaxModal>
   )

    return (
        <>
            {publicList && publicList.length > 0 && (<>
                <div className={`${styles["public-container"]}`}>
                    <div>
                    <Subtitle>Conversas compartilhadas</Subtitle>
                        <div className={styles["explanation-line"]}>Compartilhe também a sua conversa clicando no botão <scan><FaGlobe size={10} color={"#8a83eb"}/></scan> localizado no topo da tela do chat. O chat ficará público por 3 dias, ou até mudar o status novamente (é um on/off).</div>
                    </div>
                    {publicList.map((d, index) => (<div className={styles["public-line"]}
                                                        onClick={() => loadChatThread(d.id)}
                                                        key={index}
                    >
                        <div className={styles["public-title"]}>{d.title}</div>
                        {d.view_count > 0 && <div className={styles["public-title-panel"]}>
                            <div className={styles["icon"]}>
                                <svg viewBox="0 0 24 24" aria-hidden="true">
                                    <g>
                                        <path
                                            d="M8.75 21V3h2v18h-2zM18 21V8.5h2V21h-2zM4 21l.004-10h2L6 21H4zm9.248 0v-7h2v7h-2z"></path>
                                    </g>
                                </svg>
                                <div>{d.view_count}</div>
                            </div>
                        </div>}
                    </div>))}
                </div>
                {chatDetailDiv}
            </>)}
        </>
    );
}

export default PublicChats;

