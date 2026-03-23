import styles from "./SelectModal.module.css"
import React, {useState} from "react";

function SelectModal({ handleClose, handleSelect, show, optionList }) {
    const showHideClassName = show ? styles["modal"]+ " "+ styles["display-block"] : styles["modal"]+ " "+ styles["display-none"]
    const [selectedKey] = useState("");

    return (
        <div className={showHideClassName}>
            <section className={styles["modal-main"]}>
                <select
                    value={selectedKey}
                    onChange={e => handleSelect(e.target.value)}
                >
                    <option disabled selected value="">Please select an option</option>
                    {optionList.map((option, index)=> (
                        <option key={index} value={index}>{option.value}</option>
                    ))}
                </select>
                <div className={styles["modal-actions"]}>
                    <button onClick={handleClose}>Close</button>
                </div>
            </section>
        </div>
    );
};

export default SelectModal;

