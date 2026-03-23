import styles from "./ContextModal.module.css"
import React, {useContext, useEffect, useRef, useState} from "react";
import {ThemeContext} from "../../redux/ThemeContext";
import { AppContext } from '../../redux/AppContext'; // import AppContext
import {setUseMaximize} from "../../redux/actions";
import {FaXmark} from "react-icons/fa6";

function ContextModal({ handleClose, handleSave, show, clickPosition, children,
                          showClose = true,
                          closeLabel, isVisible=true, nonblocking=false }) {
    const { theme } = useContext(ThemeContext);
    const { state, dispatch } = useContext(AppContext);
    const { isMobile, useMaximize } = state;
    const modalRef = useRef(null);
    const [style, setStyle] = useState(null);
    const [useContextMaximize, setUseContextMaximize] = useState(false);

    useEffect(() => {
        if (isVisible && modalRef.current) {
            const modalRect = modalRef.current.getBoundingClientRect();
            const { innerWidth, innerHeight } = window;

            let { left, top } = clickPosition;

            // Ensure the modal is updated after content changes
            const updateModalPosition = () => {
                const modalRect = modalRef.current.getBoundingClientRect();

                // Adjust X position to keep modal within the viewport
                if (left + modalRect.width > innerWidth) {
                    left = innerWidth - modalRect.width;
                }

                // Adjust Y position to keep modal within the viewport
                // Calculate max-height to prevent overflow
                let maxHeight = innerHeight - top;
                if (top + modalRect.height > innerHeight) {
                    top = innerHeight - modalRect.height;
                    maxHeight = modalRect.height;
                }

                // Ensure the top position is never negative
                if (top < 0) {
                    top = 0;
                    maxHeight = innerHeight; // Max height is the full viewport if top is at 0
                }


                setStyle({
                    left: `${left}px`,
                    top: `${top}px`,
                    position: 'fixed',
                    maxHeight: `${maxHeight}px`,
                    overflow: 'auto' // Enable scrolling within the modal
                });
            };

            // Call once to set initial position and size
            updateModalPosition();

            // Add resize listener to update modal on viewport size change
            window.addEventListener('resize', updateModalPosition);

            // Cleanup listener on component unmount
            return () => window.removeEventListener('resize', updateModalPosition);

        }
    }, [isVisible, clickPosition, modalRef.current]); // Depend on modalRef.current to re-calculate when the modal is rendered

    useEffect(() => {
        const handleKeyDown = (event) => {
            if (event.key === 'Escape') {
                handleClose();
            }
        };

        // Add event listener
        window.addEventListener('keydown', handleKeyDown);

        // Remove event listener on cleanup
        return () => {
            window.removeEventListener('keydown', handleKeyDown);
        };
    }, [handleClose]); // Ensure useEffect runs again if handleClose changes

    // mobile is always not modeless
    const modalStyle = (!isMobile && nonblocking) ? "modal-nonblocking": "modal"

    return (
        <div className={styles[modalStyle]} onMouseDown={handleClose}>
            {!isMobile && (
            <div ref={modalRef}
                 style={style ? style : {}}
                 className={styles["modal-container"]}
                 onMouseDown={(e) => e.stopPropagation()}>
                {showClose && <div className={styles["modal-nav"]}>
                    <div className="fa-icon -larger" onClick={handleClose}>
                        <FaXmark/>
                        {/*<img*/}
                        {/*    src={theme == "dark" ? "/icons8-close-50-dark.png" : "/icons8-close-50-light.png"}*/}
                        {/*/>*/}
                    </div>
                </div>}
                <div className={styles["modal-container-inner"]}>
                    {children}
                </div>
            </div>)}

            {isMobile && (<div
                 // style={style ? style : {}}
                 className={styles["modal-fullscreen"]}
                onMouseDown={(e) => e.stopPropagation()}>
                {showClose && <div className={styles["modal-nav"]}>
                    <div className="fa-icon -larger"
                        onClick={handleClose}>
                        <FaXmark/>
                        {/*<img*/}
                        {/*    src={theme == "dark" ? "/icons8-close-50-dark.png" : "/icons8-close-50-light.png"}*/}
                        {/*/>*/}
                    </div>
                </div>}
                <div className={styles["modal-container-inner"]}>
                    {children}
                </div>
            </div>)}

        </div>
    );
}

export default ContextModal;

