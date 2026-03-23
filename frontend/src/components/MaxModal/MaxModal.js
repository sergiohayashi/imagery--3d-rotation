import styles from "./MaxModal.module.css"
import React, {useContext, useEffect, useState} from "react";
import {ThemeContext} from "../../redux/ThemeContext";
import { AppContext } from '../../redux/AppContext'; // import AppContext
import {setUseMaximize} from "../../redux/actions";
import {FaXmark} from "react-icons/fa6";
import {FaCompressAlt, FaExpandAlt} from "react-icons/fa";

function MaxModal({ handleClose, handleSave, show, children, closeLabel, useMaxFixed=false }) {
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

    return (
        <div className={showHideClassName} onMouseDown={handleClose}>
            <div className={(useMaximize || useMaxFixed)? `${styles["modal-container-maximize"]}`:`${styles["modal-container"]}`}
                 onMouseDown={(e)=> e.stopPropagation()}>
                <div className={styles["modal-nav"]}>
                    {!(useMaximize || useMaxFixed) && <>
                        <div className="fa-icon"
                            onClick={handleClose}>
                                <FaXmark/>
                        </div>
                        {!useMaxFixed && (
                        <div className="fa-icon"
                            onClick={() => dispatch(setUseMaximize(true))}>
                                <FaExpandAlt/>
                        </div>)}
                    </>
                    }
                    {(useMaximize || useMaxFixed) && <>
                        <div className="fa-icon -larger-x" onClick={handleClose}>
                            <FaXmark/>
                        </div>
                        {!useMaxFixed && (
                        <div className="fa-icon -larger-x"
                            onClick={() => dispatch(setUseMaximize(false))}>
                                <FaCompressAlt />
                        </div>)}
                    </>}
                </div>
                <div className={styles["modal-container-inner"]}>
                    {children}
                </div>
            </div>
        </div>
    );
};

export default MaxModal;

