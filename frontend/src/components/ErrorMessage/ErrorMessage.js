import React, {useState, useEffect, useContext} from 'react';
import styles from './ErrorMessage.module.css';
import {AppContext} from "../../redux/AppContext"; // import your css file
import { useErrorMessage } from '../../redux/hooks';
import {setErrorMessage, setInfoMessage} from "../../redux/actions";
import {ThemeContext} from "../../redux/ThemeContext";

function ErrorMessage() {
    const { setMessage } = useErrorMessage();
    const { state, dispatch } = useContext(AppContext);
    const { theme } = useContext(ThemeContext);
    const { errorMessage} = state;
    const [showText, setShowText] = useState(null);

    useEffect(() => {
        if (errorMessage) {
            console.log(errorMessage);

            // Handle if errorMessage is an Error/Exception instance, string, or other
            let displayText;

            if (typeof errorMessage === "string") {
                displayText = errorMessage;
            } else if (errorMessage instanceof Error) {
                displayText = errorMessage.message 
                    ? `${errorMessage.name}: ${errorMessage.message}` 
                    : errorMessage.toString();
                // If stack is useful, could append stack: 
                // if (errorMessage.stack) displayText += '\n' + errorMessage.stack;
            } else if (errorMessage && typeof errorMessage === "object") {
                // If errorMessage is a fetch error-like object with a 'detail' property
                if ('detail' in errorMessage && typeof errorMessage.detail === 'string') {
                    displayText = errorMessage.detail;
                } else {
                    // Fallback: show JSON stringified
                    displayText = JSON.stringify(errorMessage, null, 2);
                }
            } else {
                // Fallback to string coercion
                displayText = String(errorMessage);
            }

            setShowText(displayText);

            const timer = setTimeout(() => {
                setMessage(null);
            }, 10000); // 10 seconds
            return () => clearTimeout(timer);
        }
    }, [errorMessage]);

    const handleCopyContent = (content) => {
        if (navigator.clipboard) {
            navigator.clipboard.writeText(content).then(() => {
                console.log('Content copied to clipboard');
                dispatch( setInfoMessage('Content copied to clipboard'));

                // Optionally, you can display a message to the user indicating the copy was successful.
            }).catch(err => {
                console.error('Could not copy text: ', err);
            });
        } else {
            setErrorMessage( "Not supported in this browser");
        }
    };

    return errorMessage ? (
        <div className={styles["error-message"]}>

            <div
                onClick = {()=> setMessage( null)}
            >{showText}</div>
            <div onClick={() => handleCopyContent(showText)}
                 className={`${styles["copy-paste"]} icon-button-smaller-x`} title={"copy to clipboard"}>
                <img
                    src={theme == "dark" ? "/icons8-copy-50--dark.png" : "/icons8-copy-50--light.png"}
                    alt="Copy"/>
            </div>
        </div>
    ) : null;
}

export default ErrorMessage;
