import styles from "./DragAndDrop.module.css"
import {ThemeContext} from "../../redux/ThemeContext";
import React, {useContext, useEffect, useState} from "react";
import {AppContext} from "../../redux/AppContext";
import {setInfoMessage} from "../../redux/actions";

const DragAndDrop = ({ onFileDrop }) => {
    const [dragActive, setDragActive] = useState(false);
    const { theme } = useContext(ThemeContext);
    const { state, dispatch } = useContext(AppContext);

    useEffect(() => {
        // Function to enable drag area
        const enableDragArea = (e) => {
            e.preventDefault();  // Prevent default behavior for all drag events
            if (!dragActive) setDragActive(true);
        };

        // Function to disable drag area
        const disableDragArea = (e) => {
            e.preventDefault();  // Prevent default behavior for all drag events
            if (!e.relatedTarget) {
                setDragActive(false);
            }
        };

        // Function to handle drop
        const handleDrop = (e) => {
            e.preventDefault();  // This is crucial to prevent the browser from navigating
            e.stopPropagation();
            setDragActive(false);
            if (e.dataTransfer.files && e.dataTransfer.files.length> 0) {
                onFileDrop(e.dataTransfer.files);
            } else {
                dispatch( setInfoMessage( 'No file detected. Please try uploading your files using an alternative method'));
            }
        };

        // Add event listeners to the window
        window.addEventListener('dragover', enableDragArea);
        window.addEventListener('dragenter', enableDragArea);
        window.addEventListener('dragleave', disableDragArea);
        window.addEventListener('drop', handleDrop);  // Ensure this is set globally

        // Cleanup event listeners
        return () => {
            window.removeEventListener('dragover', enableDragArea);
            window.removeEventListener('dragenter', enableDragArea);
            window.removeEventListener('dragleave', disableDragArea);
            window.removeEventListener('drop', handleDrop);
        };
    }, [dragActive, onFileDrop]);  // Include dependencies here

    // Only render if drag is active
    if (!dragActive) return null;

    return (
        <div
            style={{
                position: 'absolute',
                top: 0,
                left: 0,
                width: '100%',
                height: '100%',
                pointerEvents: 'all', // Only capture events when drag is active
                zIndex: 1000, // Ensure it's on top when active, otherwise behind other content
                backgroundColor: 'var(--fullscreen-background-lighter5)',
                display: 'flex',
                justifyContent: "center",
                alignItems: "center",
            }}
        >
            <div style={{display: "flex", flexDirection: "column", alignItems: "center"}}>
            <img
                src={theme == "dark" ? "/icons8-drop-down-100.png" : "/icons8-drop-down-100.png"}
                alt="drop"/>
                <p style={{color:"var(--main-color)"}}>Drop files here...</p>
            </div>
        </div>
    );
};

export default DragAndDrop;
