import styles from "./FileMessage.module.css";
import React from "react";
import {FaFilePdf} from "react-icons/fa6";
import {FaFile, FaFileAlt} from "react-icons/fa";
import config from "../../config";

export const handleLocalFile= (imageUrl) => {
    if (!imageUrl) return null;
    if (imageUrl.startsWith("http")) {
        return imageUrl;
    } else { 
        // example: file:///home/hayashi/phd/imagery/projects/simplechat/problems/spatialviz/dataset-eval2-1001--3d-rotation-level-0/images/0-3-3-1-5.png
        // the server mount the local files to in /home/hayashi/phd/imagery/projects/simplechat/problems/spatialviz
        // imageUrl = imageUrl.replace("file:///home/hayashi/phd/imagery/projects/simplechat/problems/spatialviz", "")
        // imageUrl = imageUrl.replace("file:///home/hayashi/phd/imagery/projects/imagery--3d-rotation/data/spatialviz", "")
        imageUrl = imageUrl.replace("file://", "")
        return config.apiUrl + imageUrl
    }
}


export const getFileIcon = (contentType, fileUrl) => {
    // Fallback based on extension if no content_type
    const ext = fileUrl ? fileUrl.split('.').pop().toLowerCase() : "";
    const type = contentType?.split('/')[0];

    if (type === "video") {
        return (
            <video className={styles["video-in-thread-as-icon"]}
                src={fileUrl}
                controls
            />
        )
            ;
    }
    if (type === "image" || /\.(jpg|jpeg|png|gif|webp|bmp|svg)$/.test(ext)) {
        return (
            <img className={styles["image-in-thread-as-icon"]}
                 src={fileUrl}/>
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



export const FileMessage = ({ message }) => {
    if (!message.file_url) return null;

    const fileUrl = handleLocalFile(message?.file_url);

    return (
        <div className="file-message-card">
            <a href={fileUrl} target="_blank" rel="noopener noreferrer" className={styles["file-link"]}>
                {getFileIcon(message?.content_type, fileUrl)}
                <span className="file-meta">
                    <span className="file-name">{getFileName(message.file_name)}</span>
                </span>
            </a>
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