import React, {useContext, useEffect, useState} from "react";
import styles from "./DailyUsage.module.css"
// import { getApi } from '../../services/apiService';
import {AppContext} from "../../redux/AppContext";
import {useMsal} from "@azure/msal-react";
import {ThemeContext} from "../../redux/ThemeContext";
import MaxModal from "../MaxModal/MaxModal";
import {useApi} from "../../hooks/useApi";
import {Subtitle} from "../Headings/Heading";

function DailyUsage() {
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
        const result = await api.get("/api/metrics/daily_usage");
        setUsage( result?.data?.usage)
    }

    return (
        <div className={styles["container"]}>
            <Subtitle>Daily Usage</Subtitle>
            <div className={styles['usage-content']}>
                {usage.map((r, index) => (
                    <div key={index} className={styles['usage-line']}>
                        <div>{r._id}</div>
                        <div>{r.count}</div>
                    </div>
                ))}
            </div>
        </div>
    )
}


export default DailyUsage;
