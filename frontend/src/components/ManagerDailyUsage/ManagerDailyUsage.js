import React, {useContext, useEffect, useState} from "react";
import styles from "./ManagerDailyUsage.module.css"
// import { getApi } from '../../services/apiService';
import {AppContext} from "../../redux/AppContext";
import {useMsal} from "@azure/msal-react";
import {ThemeContext} from "../../redux/ThemeContext";
import MaxModal from "../MaxModal/MaxModal";
import {useApi} from "../../hooks/useApi";
import {Subtitle} from "../Headings/Heading";

function ManagerDailyUsage() {
    const { state, dispatch } = useContext(AppContext);
    const [usage, setUsage] = useState([]);
    const { instance } = useMsal();
    const { theme } = useContext(ThemeContext);
    const api = useApi();

    useEffect(() => {
        (async () => {
            try {
                await loadUsage();
            } catch (error) {
                // silent error..
                console.error("Failed to load monthly usage:", error);
            }
        })();
    }, []);


    const loadUsage = async () => {
        const result = await api.get("/api/manager/metrics/daily_usage");
        setUsage(result?.data)
    }

    return (
        <div className={styles["container"]}>
            <Subtitle>Daily Usage</Subtitle>
            <div className={styles["tenant-container"]}>
                {Object.entries(usage).map(([tenant, records]) => (
                    <div key={tenant} className={styles["tenant-section"]}>
                        <h3>{tenant}</h3>
                        {records.map((record, index) => (
                            <div key={index} className={styles["usage-line"]}>
                                <div>{record.date}</div>
                                <div>{record.count<= 0? '-': record.count}</div>
                            </div>
                        ))}
                    </div>
                ))}
            </div>
        </div>
    );
}


export default ManagerDailyUsage;
