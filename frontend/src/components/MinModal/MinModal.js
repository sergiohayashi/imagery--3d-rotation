import styles from "./MinModal.module.css"

function MinModal({ handleClose, handleSave, show, children, closeLabel }) {
    const showHideClassName = show ? `${styles["modal"]} ${styles["display-block"]}` :
        `${styles["modal"]} ${styles["display-none"]}`;
    return (
        <div className={showHideClassName}>
            <div className={styles["modal-container"]}>
                <div className={styles["modal-container-inner"]}>
                    {children}
                </div>
                <div className={styles["modal-actions"]}>
                    <button onClick={handleClose}  className="button">{closeLabel || "Cancel"}</button>
                    {handleSave && <button onClick={handleSave}  className="button">Save</button>}
                </div>
            </div>
        </div>
    );
};

export default MinModal;

