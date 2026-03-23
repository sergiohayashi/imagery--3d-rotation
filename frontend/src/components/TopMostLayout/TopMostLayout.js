import TopLayout from "../TopLayout/TopLayout";
import React, {useContext, useEffect, useState} from "react";
import {AppContext} from "../../redux/AppContext";
import styles from './TopMostLayout.module.css'
import TopMostNavBar from "../TopMostNavBar/TopMostNavBar";
import {Route, Routes} from "react-router-dom";
import Metrics from "../Metrics/Metrics";
import Project from "../Project/Project";
import Settings from "../Settings/Settings";
import {ThemeContext} from "../../redux/ThemeContext";
import ManagerTop from "../ManagerTop/ManagerTop";
import {CiMenuFries} from "react-icons/ci";
// import Feedback from "../Feedback/Feedback";



function TopMostLayout() {
    const { theme } = useContext(ThemeContext);
    const { state, dispatch } = useContext(AppContext);
    const { isMobile } = state;
    const [showNavBar, setShowNavBar] = useState(false);

    useEffect(() => {
        document.body.className = theme;
    }, [theme]);

    const divNavBar = isMobile? (<>
        <div className={styles['toggler']} onClick={()=> setShowNavBar(!showNavBar)}>
            <div className={"fa-icon"}>
                <CiMenuFries/>
            </div>
        </div>
        <div className={`${styles["navbar"]} ${showNavBar?'':styles['hide']}`}>
            <TopMostNavBar/>
        </div>
        </>
    ) : (
        <div className={styles["navbar"]}>
            <TopMostNavBar/>
        </div>
    )

    return (
        <div className={styles["container"]}>
            {/* <div>TopMostLayout.js here!</div> */}

            {/* {divNavBar} */}
            <div className={styles["main-app"]}>
                <Routes>
                    <Route path="/manager/*" element={<ManagerTop />} />
                    <Route path="/metrics" element={<Metrics />} />
                    {/*<Route path="/chat/:chatIdFromUrl" element={<TopLayout />} />*/}
                    <Route path="/workspace" element={<Project />} />
                    <Route path="/settings" element={<Settings />} />
                    {/*<Route path="/feedback" element={<Feedback />} />*/}
                    <Route path="/*" element={<TopLayout />} />
                </Routes>
            </div>
        </div>
    )


}

export default TopMostLayout;
