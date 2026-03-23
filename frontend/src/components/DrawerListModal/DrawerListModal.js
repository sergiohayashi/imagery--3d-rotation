import styles from "./DrawerListModal.module.css"
import React, {useContext, useState} from "react";
import {ThemeContext} from "../../redux/ThemeContext";
import {AppContext} from "../../redux/AppContext";

function DrawerListModal({ handleClose, handleSave, style, show, children, closeLabel }) {
    // const [isMaximized, setMaximize] = useState(false);
    const { theme } = useContext(ThemeContext);
    const { state } = useContext(AppContext);
    const { isMobile } = state;


    const showHideClassName = show ? `${styles["modal"]} ${styles["display-block"]}` :
        `${styles["modal"]} ${styles["display-none"]}`;

    return (
        <div className={showHideClassName} onMouseDown={handleClose}>
            <div className={`${styles["modal-container"]} open`} style={isMobile?{}:style}
                 onMouseDown={(e)=> e.stopPropagation()}
            >
                <div className={styles["modal-nav"]}>
                    <div className="icon-button-smaller">
                        <a onClick={handleClose}>
                            <img
                                src ={theme == "dark"? "/icons8-close-50-dark.png": "/icons8-close-50-light.png"}
                            />
                        </a>
                    </div>
                </div>
                <div className={styles["modal-container-inner"]}>
                    {children}
                </div>
            </div>
        </div>
    );
};

export default DrawerListModal;

