import AppRouter from "../AppRouter/AppRouter";
import React, {useContext} from "react";
import {AppContext} from "../../redux/AppContext";
import styles from './TopLayout.module.css'
import 'rc-slider/assets/index.css';
import TopMenu from "./TopMenu";
import config from "../../config";

function TopLayout() {
    const { state, dispatch } = useContext(AppContext);
    const { projectList, currentProject, showNav, isMobile } = state;

    // {/* {currentProject && projectList && <AppRouter/>} */}

    return (
        <div className={`${styles["app-top"]}`}>
            {/* <div className={styles["top-level-header"]}>
                <TopMenu/>
            </div> */}
            <h3>Limits of Imagery Reasoning in Frontier LLM Models</h3>
            <div className={styles["top-level-main"]}>
                <AppRouter/>
            </div>
        </div>
    )
}

export default TopLayout;
