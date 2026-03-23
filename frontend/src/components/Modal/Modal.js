import styles from "./Modal.module.css"

function Modal({ handleClose, handleSave, show, children, closeLabel }) {
    const showHideClassName = show ? `${styles["modal"]} ${styles["display-block"]}` :
        `${styles["modal"]} ${styles["display-none"]}`;
    return (
        <div className={showHideClassName}>
            <div className={styles["modal-container"]}>
                <div className={styles["modal-container-inner"]}>
                    {children}
                </div>
                <div className={styles["modal-actions"]}>
                    <button onClick={handleClose}>{closeLabel || "Cancel"}</button>
                    {handleSave && <button onClick={handleSave}>Save</button>}
                </div>
            </div>
        </div>
    );
};

export default Modal;

