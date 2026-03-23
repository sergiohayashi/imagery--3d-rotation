import React, {useState, useEffect, useContext} from 'react';
import {AppContext} from "../../redux/AppContext";
import styles from "./SharedChat.module.css"
import { useParams } from 'react-router-dom';
import {ThemeContext} from "../../redux/ThemeContext";
import config from "../../config"
import axios from 'axios';
import {setErrorMessage, setInfoMessage, setUseMaximize} from "../../redux/actions";
import FullMarkdown from "../FullMarkdown/FullMarkdown";
import {FaDownload} from "react-icons/fa6";
import {FaMoon, FaSun} from "react-icons/fa";
import Logo from "../Logo/Logo";
import {FileMessage} from "./FileMessage";
import MessageCard from "./MessageCard";
import MessageCardForShared from "./MessageCardForShared";


function SharedChat() {
    const {guid} = useParams();
    const [content, setContent] = useState(null);
    const [error, setError] = useState(null);
    const {state, dispatch} = useContext(AppContext);
    const {isMobile} = state;
    const [augmentedMessage, setAugmentedMessage] = useState(null);
    const [showAugmentedMessage, setShowAugmentedMessage] = useState(false);
    const {theme, switchTheme} = useContext(ThemeContext);

    useEffect(() => {
        document.body.className = theme;
    }, [theme]);


    useEffect(() => {
        dispatch(setUseMaximize(true));

        setContent({
            title: "Titulo " + guid,
            description: "Description"
        })
        axios.get(`${config.apiUrl}/api/public/shared_chats/${guid}/thread`)
            .then(response => {
                setContent(response.data);
            })
            .catch(error => {
                if (error.response?.data?.detail)
                    setError(error.response?.data?.detail)
                else
                    setError(error.message);
            });
    }, [guid]);

    const sanitizeFilename = (name) => {
        return name.replace(/[/\\?%*:|"<>]/g, '-');
    }
    const downloadChat = (text, filename) => {
        if (!content.entries) return;

        // flatten
        const flatten_messages = [];
        for (let m of content.entries) {
            for (let entry of m) {
                flatten_messages.push(entry);
            }
        }
        text = flatten_messages.map(m => `${m.role}${m.role==="assistant"?"("+m.meta?.model+")":""}: ${m.content}`).join('\n\n');
        // text = content.entries.map(m => `${m.role}: ${m.content}`).join('\n\n');

        // Create a blob of the text
        const blob = new Blob([text], {type: 'text/plain'});

        // Create a link to download the blob
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = "Imagery - " + sanitizeFilename(content.title || "Chat") + ".txt";

        // Append the link to the body, click it, and then remove it
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    };

    const header = (
        <>
            <div className={styles["header-row"]}>
                <h3 className={styles["header"]}
                    onClick={() => {
                        window.location.href = config.frontendUrl;
                    }}
                >Imagery</h3>
                <div className={styles["header-buttons"]}>
                    <div className="icon-button-smaller"
                         onClick={switchTheme}>
                        {theme === "dark" ? <FaSun title="Light mode"/> : <FaMoon title="Dark mode"/>}
                    </div>
                    <div onClick={() => downloadChat()}
                         className="fa-icon" title={"download"}>
                        <FaDownload/>
                    </div>
                </div>
            </div>
            <div className={styles["header-line"]}></div>
        </>
    )

    if (error) {
        return (
            <div className={styles['container']}>
                {header}
                <div className={styles["error"]}>{error}</div>
            </div>)
    }

    return (
        <div className={styles['container']}>
            {header}
            {content && content.entries && (
                <div>
                    <h1>{content.title}</h1>
                    <div className={styles["published"]}>
                        Created {new Date(content.created_at).toString()}.
                        Expires {new Date(content.shared_id_expire_date).toDateString()}</div>
                    <div className={`code-view-in-chat ${styles["chat-conversation-top"]}`}>
                        {content.entries.map((message, index) => (<>
                            <MessageCardForShared
                                {...{ /* adjust to the parameters expected by MessageBlock */
                                    message,
                                    index,
                                }}
                            />
                        </>))}
                    </div>
                </div>
            )}
        </div>
    );
}

export default SharedChat;
