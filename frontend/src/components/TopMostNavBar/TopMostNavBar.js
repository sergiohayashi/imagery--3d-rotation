import React, {useContext, useEffect, useRef, useState} from "react";
import {AppContext} from "../../redux/AppContext";
import styles from './TopMostNavBar.module.css'
import {ThemeContext} from "../../redux/ThemeContext";
import {Link, useNavigate} from "react-router-dom";
import {
    setBalance,
    setChatLayout,
    setCurrentUsage,
    setDisableFromat,
    setInfoMessage,
    setShowMultiColumn
} from "../../redux/actions";
import Busy from "../Busy/Busy";
import {useApi} from "../../hooks/useApi";
import {useAuth} from "../../context/AuthContext";
import {
    FaUserTie,
    FaComments,
    FaFileAlt,
    FaSun,
    FaMoon,
    FaChartBar,
    FaSignOutAlt, FaRegImages,
} from 'react-icons/fa';
import {IoFolderSharp, IoSettingsOutline} from "react-icons/io5";
import {FaDisplay} from "react-icons/fa6";
import {MdCode, MdCodeOff} from "react-icons/md";
import {LuPanelBottom, LuPanelRight} from "react-icons/lu";
import config from "../../config";
import {LiaGripVerticalSolid} from "react-icons/lia";
import {BsViewStacked} from "react-icons/bs";


function TopMostNavBar() {
    const {theme, switchTheme} = useContext(ThemeContext);
    const navigate = useNavigate();
    const {state, dispatch} = useContext(AppContext);
    const {chatLayout, currentUsage, profile, isDisableFormat, waiting, balance, showMultiColumn} = state;
    const {logout} = useAuth();

    const api = useApi();

    // useEffect(() => {
    //     const loadMetric = () => {
    //         api.get('/api/metrics/monthly_usage/current')
    //             .then(response => {
    //                 dispatch(setCurrentUsage(response.data));
    //             })
    //             .catch((error) => { /*error handled in apiService*/
    //             });

    //         api.get("/api/account/balance")
    //             .then(response => {
    //                 dispatch(setBalance(response?.data));
    //             })
    //             .catch((error) => { /*error handled in apiService*/
    //             });
    //     }
    //     loadMetric()
    // }, [])

    const switchMultiColumn = () => {
        dispatch(setShowMultiColumn(!showMultiColumn));
    }

    const rotateLayout = () => {
        dispatch(setChatLayout(chatLayout === "bottom" ? "side" : "bottom"));
    }

    const [loading, setLoading] = useState(false);

    return (
        <div className={styles["container"]}>
            <div className={styles["top"]}>
                <Link className={`${config.is_partner ? styles["logo-partner"] : styles["logo"]}`}
                      to="/chat">
                    <img
                        src={"/android-chrome-512x512.png"}
                        alt="App Logo"
                        className={`${styles["app-logo"]} ${waiting ? 'fade-anim' : ''}`}
                    />
                </Link>
                {/* {(profile?.permissions || []).includes('manager') &&
                    <div className={"fa-icon -larger -color-blue"}
                         onClick={() => {
                             navigate('/manager')
                         }}>
                        <FaUserTie title="Manager"/>
                    </div>}
                <div className={"fa-icon -larger"}
                     onClick={() => {
                         navigate('/system_message')
                     }}>
                    <FaDisplay title="System message"/>
                </div>
                <div className={"fa-icon -larger"}
                     onClick={() => {
                         navigate('/context_artifact')
                     }}>
                    <FaFileAlt title="Predefined context"/>
                </div> */}
                {/* <div className={"fa-icon -larger"}
                     onClick={() => {
                         navigate('/chat')
                     }}>
                    <FaComments title="Chat"/>
                </div> */}
                {/* <div className={"fa-icon -larger"}
                     onClick={() => {
                         navigate('/files')
                     }}>
                    <FaRegImages  title="Files"/>
                </div> */}
                <div className={"fa-icon -larger"}
                     onClick={rotateLayout}>
                    {chatLayout === "bottom" ? <LuPanelRight title="Side layout"/> :
                            <LuPanelBottom title="Bottom layout"/>}
                </div>
                <div className={"fa-icon -larger"}
                     title={isDisableFormat ? "Enable format" : "Disable format"}
                     onClick={() => dispatch(setDisableFromat(!isDisableFormat))}>
                    {isDisableFormat ? <MdCode/> : <MdCodeOff/>}
                </div>
                {/* <div className={"fa-icon -larger"}
                     onClick={switchMultiColumn}>
                    {showMultiColumn ? <BsViewStacked title="Show multi-chat as single column"/> :
                        <LiaGripVerticalSolid title="Show multi-chat as multi column"/>}
                </div> */}
            </div>
            <div className={styles["bottom"]}>
                <div className={"fa-icon -larger"}
                     onClick={switchTheme}>
                    {theme === "dark" ? <FaSun title="Light mode"/> : <FaMoon title="Dark mode"/>}
                </div>
                {/* <div className={"fa-icon -larger"}
                     title="Workspace"
                     onClick={() => {
                         navigate('/workspace')
                     }}>
                    <IoFolderSharp/>
                </div>
                <div className={`${styles["current-usage-count-container"]}`}>
                    <div className={"fa-icon -larger"}
                         title="Metrics"
                         onClick={() => {
                             navigate('/metrics')
                         }}>
                        <FaChartBar/>
                    </div>
                    <div className={styles["current-usage-count"]}>{currentUsage}</div>
                </div>
                <div className={`${styles["current-usage-count-container"]}`}>
                    <div className={"fa-icon -larger"}
                         onClick={() => {
                             navigate('/settings')
                         }}>
                        <IoSettingsOutline/>
                    </div>
                    <div className={styles["current-cost-estimate-count"]}>{balance?.balance}</div>
                </div> */}
                <div className={"fa-icon -larger"}
                     title="Logout"
                     onClick={() => {
                         if (window.confirm("Are you sure you want to logout?")) {
                             logout();
                         }
                     }}>
                    <FaSignOutAlt/>
                </div>
            </div>
            {loading && <Busy/>}
        </div>
    )
}

export default TopMostNavBar;
