import styles from "./ManagerMetrics.module.css"
import Ranking from "../Ranking/Ranking";
import MonthlyUsage from "../MonthlyUsage/MonthlyUsage";
import DailyUsage from "../DailyUsage/DailyUsage";
import React, {useContext} from "react";
import {useNavigate} from "react-router-dom";
import {ThemeContext} from "../../redux/ThemeContext";
import {FaAngleLeft} from "react-icons/fa";
import {Title} from "../Headings/Heading";
import MonthlyModelUsage from "../MonthlyModelUsage/MonthlyModelUsage";
import ManagerDailyUsage from "../ManagerDailyUsage/ManagerDailyUsage";

function ManagerMetrics() {
    const { theme } = useContext(ThemeContext);
    const navigate = useNavigate();
    return (
        <div className={styles['container']}>
            {/*<div className={"title-with-back"}>*/}
            {/*    <div className={"fa-icon"}*/}
            {/*         onClick={() => navigate(-1)}>*/}
            {/*        <FaAngleLeft/>*/}
            {/*    </div>*/}
            {/*    <Title>Metrics</Title>*/}
            {/*    /!*<img src={theme == "dark" ? "/icons8-previous-dark-50.png" : "/icons8-previous-light-50.png"}*!/*/}
            {/*    /!*     alt="back"/>*!/*/}
            {/*</div>*/}
            <div className={styles['metrics-container']}>
                <ManagerDailyUsage/>
            </div>
        </div>
    )
}


export default ManagerMetrics;
