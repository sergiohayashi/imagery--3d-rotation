import React, {useContext, useEffect, useState} from "react";
import styles from "./MonthlyModelUsage.module.css"
// import { getApi } from '../../services/apiService';
import {AppContext} from "../../redux/AppContext";
import {useMsal} from "@azure/msal-react";
import {ThemeContext} from "../../redux/ThemeContext";
import MaxModal from "../MaxModal/MaxModal";
import {useApi} from "../../hooks/useApi";
import {SectionTitle, Subtitle} from "../Headings/Heading";

function MonthlyModelUsage() {
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
        const result = await api.get("/api/metrics/monthly_models_usage");
        setUsage( result?.data?.usage)
    }

    return (
        <div className={styles["container"]}>
            <Subtitle>Monthly Model Usage</Subtitle>
            <div className={styles['usage-content']}>
                {Object.entries(
                    usage.reduce((acc, r) => {
                        const {year, month, model} = r._id;
                        const count = r.count;

                        // Group by year and month
                        const key = `${year}-${month}`;
                        if (!acc[key]) {
                            acc[key] = [];
                        }
                        acc[key].push({model, count});
                        return acc;
                    }, {})
                ).map(([key, models]) => {
                    const [year, month] = key.split("-");
                    return (
                        <div key={key} className={styles['usage-group']}>
                            <div className={styles['sub-title']}><Subtitle>{`${year}/${month}`}</Subtitle></div>
                            <table className={styles['usage-table']}>
                                <tbody>
                                {models.map((modelData, index) => (
                                    <tr key={index} className={styles["usage-line"]}>
                                        <td>{modelData.model}</td>
                                        <td>{modelData.count}</td>
                                    </tr>
                                ))}
                                </tbody>
                            </table>
                        </div>
                    );
                })}
            </div>
        </div>

    )
}


export default MonthlyModelUsage;
