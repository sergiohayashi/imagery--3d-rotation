import styles from "./Busy.module.css"
import {ThemeContext} from "../../redux/ThemeContext";
import React, {useContext, useEffect, useState} from "react";
import {LiaTruckLoadingSolid} from "react-icons/lia";

function Busy() {
    const { theme } = useContext(ThemeContext);
    return (
        <div className={styles["loading-window"]}>
            <img className={`loading-anim ${styles["loading-img"]}`}
                  // src={theme == "dark" ? "/icons8-loading-50-dark.png" : "/icons8-loading-50-light.png"}
                  // src={theme == "dark" ? "/icons8-loading-100--dark.png" : "/icons8-loading-100--light.png"}
                 src={theme == "dark" ? "/icons8-loading-100-dark.png" : "/icons8-loading-100-light.png"}
            ></img>
        </div>
    );
}

export default Busy;

