import styles from "./FileCard.module.css";
import React, {useContext} from "react";
import {FaFilePdf, FaTrash} from "react-icons/fa6";
import {FaFile, FaFileAlt} from "react-icons/fa";
import {simpleDateFormatter} from "../../helpers/formatters";
import {BsChat, BsChatFill} from "react-icons/bs";
import {setCurrentChatId} from "../../redux/actions";
import {AppContext} from "../../redux/AppContext";
import {useNavigate} from "react-router-dom";
import {useApi} from "../../hooks/useApi";


function LazyVideo({ src, poster }) {
    const videoRef = React.useRef(null);
    const [ready, setReady] = React.useState(false);

    React.useEffect(() => {
        const ob = new IntersectionObserver(
            ([entry]) => entry.isIntersecting && setReady(true),
            { threshold: 0.25 }                 // 25 % in view
        );
        videoRef.current && ob.observe(videoRef.current);
        return () => ob.disconnect();
    }, []);

    return (
        <video
            ref={videoRef}
            controls
            preload="none"
            poster={poster}         // lightweight jpg
            src={ready ? src : undefined}
            style={{ width: '100%' }}
        />
    );
}


export const getFileIcon = (contentType, fileUrl) => {
    // Fallback based on extension if no content_type
    const ext = fileUrl ? fileUrl.split('.').pop().toLowerCase() : "";
    const type = contentType?.split('/')[0];

    if (type === "video") {
        return (
            // <LazyVideo
            //     src={fileUrl}/>
            <video
                src={fileUrl}
                preload="metadata"
                controls
                className={styles["video-in-thread-as-icon"]}
                />
        )
            ;
    }
    if (type === "image" || /\.(jpg|jpeg|png|gif|webp|bmp|svg)$/.test(ext)) {
        return (
            <img className={styles["image-in-thread-as-icon"]}
                 src={fileUrl}
                 loading="lazy"
                 decoding="async"
            />
        )
            ;
    }
    if (contentType === "application/pdf" || ext === "pdf") {
        return (
            <span className={`${styles["file-icon"]} ${styles["pdf-icon"]}`}>
        <FaFilePdf  />
      </span>
        );
    }
    if (
        contentType === "text/plain" ||
        /\.(txt|md|csv|log)$/i.test(ext)
    ) {
        return (
            <span className={`${styles["file-icon"]} ${styles["text-icon"]}`}>
        <FaFileAlt  />
      </span>
        );
    }
    // Add more types as you like
    return (
        <span className={`${styles["file-icon"]} ${styles["file-generic-icon"]}`}>
      <FaFile />
    </span>
    );
};

export const FileCard = ({ message, onRefresh }) => {
    const { state, dispatch } = useContext(AppContext);
    const navigate = useNavigate();
    const api = useApi();

    if (!message.file_url) return null;

    const handleChatHistoryClick = async (e, _chatId) => {
        const openInNewTab = e.ctrlKey || e.metaKey || e.button === 1;
        if (openInNewTab) {
            window.open(`/#/chat/${_chatId}`, '_blank', 'noopener,noreferrer');
        } else {
            await dispatch(setCurrentChatId(_chatId))
            navigate(`/chat/${_chatId}`);
        }
    }

    const handleFileDelete= async (id) => {
        if (window.confirm(`Delete file and chat ?`)) {
            await api.delete(`/api/files/${id}`);
            if (onRefresh) await onRefresh();
        }
    }

    return (
        <div className={styles["file-card"]}>
            {getFileIcon(message?.content_type, message?.file_url)}
            <a href={message.file_url} target="_blank" rel="noopener noreferrer" className={styles["file-link"]}>
                <div className={styles["file-meta"]}>
                    <div className={styles["file-name"]}>{getFileName(message.file_name)}</div>
                    <div className={styles['file-name']}>{simpleDateFormatter(message.created_at)}</div>
                </div>
            </a>
            <div className={styles["control-bar"]}>
                <div className={"fa-icon -smaller"}
                    title = "Open chat"
                    onClick = {(e) => handleChatHistoryClick(e, message.chat_id)}
                >
                    <BsChatFill />
                </div>
                <div className={"fa-icon -smaller -delete"}
                     title = "Delete file and chat"
                     onClick = {(e) => handleFileDelete(message.id)}
                >
                    <FaTrash />
                </div>
            </div>
        </div>
    );
};


export const FileMessageForOutput = ({ output }) => {
    if (!output.file_url) return null;

    return (
        <div className="file-message-card">
            <a href={output.file_url} target="_blank" rel="noopener noreferrer" className={styles["file-link"]}>
                {getFileIcon(output?.content_type, output?.file_url)}
                <span className="file-meta">
                    <span className="file-name">{output.file_name}</span>
                </span>
            </a>
        </div>
    );
};


export const getFileName = (url) => {
    try {
        const decodedUrl = decodeURI(url);
        return decodedUrl.split('/').pop().split('?')[0];
    } catch {
        return url;
    }
};