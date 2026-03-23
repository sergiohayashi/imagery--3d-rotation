import React, {useState, useEffect, useContext} from 'react';
import styles from './InfoMessage.module.css';
import {AppContext} from "../../redux/AppContext"; // import your css file
import {setErrorMessage, setInfoMessage} from '../../redux/actions';

function InfoMessage() {
    const {state, dispatch} = useContext(AppContext);
    // const { setMessage } = useInfoMessage();
    const [copied, setCopied] = useState(false);

    useEffect(() => {
        if (state.infoMessage) {
            console.log( state.infoMessage);
            setCopied(false);
            const timer = setTimeout(() => {
                dispatch( setInfoMessage( null));
            }, 4000); // 5 seconds
            return () => clearTimeout(timer);
        }
    }, [state.infoMessage]);

    const handleCopyContent = (content) => {
        if (navigator.clipboard) {
            navigator.clipboard.writeText(content).then(() => {
                setCopied(true);
               // console.log('Content copied to clipboard');
                // dispatch( setInfoMessage('Content copied to clipboard'));

                // Optionally, you can display a message to the user indicating the copy was successful.
            }).catch(err => {
                console.error('Could not copy text: ', err);
            });
        } else {
            // setErrorMessage( "Not supported in this browser");
        }
    };

    let text = typeof(state.infoMessage) == "string"?state.infoMessage:JSON.stringify(state.infoMessage)

    return state.infoMessage ? (
        <div className={styles["info-message"]}
             onClick={() => handleCopyContent(text)}
        >
            <div  className={styles["inner-div"]}>
                {text}
                {copied && <><b>copied!</b></>}
            </div>
        </div>
    ) : null;
}

export default InfoMessage;
