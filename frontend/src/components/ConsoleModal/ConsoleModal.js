import styles from "./ConsoleModal.module.css"
import React, {useContext, useEffect, useState} from "react";
import {ThemeContext} from "../../redux/ThemeContext";
import { AppContext } from '../../redux/AppContext'; // import AppContext
import {setUseMaximize} from "../../redux/actions";

function ConsoleModal({ handleClose, handleSave, show, children, closeLabel }) {
    // const [useMaximize, setMaximize] = useState(false);
    const { theme } = useContext(ThemeContext);
    const { state, dispatch } = useContext(AppContext);
    const { isMobile, useMaximize } = state;

    useEffect(()=> {
        if (isMobile) {
            dispatch(setUseMaximize(true));
        }
    }, [isMobile])

    const showHideClassName = show ? `${styles["modal"]} ${styles["display-block"]}` :
        `${styles["modal"]} ${styles["display-none"]}`;

    const nav = (
        <div className={styles["modal-nav"]}>
            {!useMaximize && <>
                <div className="icon-button-smaller">
                    <a onClick={handleClose}>
                        <img
                            src={theme == "dark" ? "/icons8-close-50-dark.png" : "/icons8-close-50-light.png"}
                        />
                    </a>
                </div>
                <div className="icon-button-smaller">
                    <a onClick={() => dispatch(setUseMaximize(true))}>
                        <img
                            src={theme == "dark" ? "/icons8-maximize-arr-50-dark.png" : "/icons8-maximize-arr-50-light.png"}
                        />
                    </a>
                </div>
            </>
            }
            {useMaximize && <>
                <div className="icon-button">
                    <a onClick={handleClose}>
                        <img
                            src={theme == "dark" ? "/icons8-close-50-dark.png" : "/icons8-close-50-light.png"}
                        />
                    </a>
                </div>
                <div className="icon-button">
                    <a onClick={() => dispatch(setUseMaximize(false))}>
                        <img
                            src={theme == "dark" || useMaximize ? "/icons8-compress-arr-50-dark.png" : "/icons8-compress-arr-50-light.png"}
                        />
                    </a>
                </div>
            </>}
        </div>
    )

    return (
        <div className={showHideClassName} onMouseDown={handleClose}>
            {/*<div className={useMaximize ? `${styles["modal-container-maximize"]}` : `${styles["modal-container"]}`}*/}
            {/*     onMouseDown={(e) => e.stopPropagation()}>*/}
            <div className={styles["modal-container"]}
                 onMouseDown={(e) => e.stopPropagation()}>
                {/*{nav}*/}
                <div className={styles["modal-container-inner"]}>
                    {children}
                </div>
                <div className={styles["modal-actions"]}>
                    {/*<button onClick={handleClose}>{closeLabel || "Cancel"}</button>*/}
                    {handleSave && <button onClick={handleSave} className="button">Save</button>}
                </div>
            </div>
        </div>
    );
};

export default ConsoleModal;

