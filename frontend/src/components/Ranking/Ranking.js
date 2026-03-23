import React, {useContext, useEffect, useState} from "react";
import styles from "./Ranking.module.css"
// import { getApi } from '../../services/apiService';
import {AppContext} from "../../redux/AppContext";
import {useMsal} from "@azure/msal-react";
import {ThemeContext} from "../../redux/ThemeContext";
import {useApi} from "../../hooks/useApi";
import {FaAngleDown, FaAngleLeft, FaAngleRight, FaAngleUp} from "react-icons/fa";
import {SectionTitle, Subtitle, Title} from "../Headings/Heading";

function Ranking() {
    const { state, dispatch } = useContext(AppContext);
    const [ranking, setRanking] = useState([]);
    // const { chatId } = state;
    const { instance } = useMsal();
    const { theme } = useContext(ThemeContext);
    const [isFullLoad, setFullLoad] = useState(false);
    const [month, setMonth] = useState(null);
    const [year, setYear] = useState(null);
    const api = useApi();
    const [excludeNameFromRanking, setExcludeNameFromRanking] = useState(false);

    useEffect(() => {
        (async () => {
            try {
                await loadRanking(month, year);
            } catch (error) {
                // silent error..
                console.error("Failed to load ranking:", error);
            }
        })();
    }, [isFullLoad]);

    useEffect(()=> {
        const load = () => {
            api.get("/api/account/exclude-from-ranking")
                .then(response => {
                    setExcludeNameFromRanking(response.data?.status)
                })
                .catch((error)=> { /*error handled in apiService*/});
        }
        load();
    }, [])

    const handleSwitchExcludeNameFromRanking = async () => {
        try {
            // setWorking( true);
            const response = await api.put("/api/account/exclude-from-ranking/switch")
            setExcludeNameFromRanking(response.data?.status);

            await loadRanking(month, year);
        } finally {
            // setWorking(false);
        }
    }


    const loadRanking = async (month=null,year=null) => {
        const top = isFullLoad? 999: 3;
        const result = await api.get("/api/metrics/ranking", {
           params: {
               top: top,
               month: month,
               year: year,
           }
        });
        setRanking( result?.data?.ranking);
        setMonth( result?.data?.month)
        setYear( result?.data?.year)
    }

    const medals = {
        "dark": [
            "/icons8-gold-medal-40.png",
            "/icons8-silver-medal-40.png",
            "/icons8-bronze-medal-40.png",
            "/icons8-circled-4-50--dark.png",
            "/icons8-circled-5-50--dark.png",
        ],
        "light": [
            "/icons8-gold-medal-40.png",
            "/icons8-silver-medal-40.png",
            "/icons8-bronze-medal-40.png",
            "/icons8-circled-4-50--light.png",
            "/icons8-circled-5-50--light.png",
        ]
    }

    const isCurrent= () => {
        return month === new Date().getMonth() && year === new Date().getFullYear();
    }

    const isEpoch = () => {
        return month === 9 && year === 2023;
    }


    return (
        <div className={styles['ranking-container']}>
            {/*<Subtitle>This month's usage ranking</Subtitle>*/}
            <div className={"row-center"}>
                <input type="checkbox"
                       checked={excludeNameFromRanking}
                       onChange={(e) => {
                           handleSwitchExcludeNameFromRanking()
                       }}
                /><div>Exclude my name from the list</div>
            </div>
            <div className={styles['ranking-period']}>
                <div className={styles["period-left-button"]}>
                    <div onClick={() => {
                        if (isCurrent()) return;
                        loadRanking(month == 11 ? 0 : (month + 1), month == 11 ? (year + 1) : year);
                    }}

                         className="fa-icon" title={"left"}>
                        <FaAngleLeft/>
                        {/*<img*/}
                        {/*    src={theme == "dark" ? "/icons8-c-50.png" : "/icons8-previous-light-50.png"}/>*/}
                    </div>
                </div>
                <SectionTitle>{year}/{month + 1}</SectionTitle>
                <div className={styles["period-right-button"]}>
                    <div onClick={() => {
                        if (isEpoch()) return;
                        loadRanking(month == 0 ? 11 : month - 1, month == 0 ? year - 1 : year);
                    }}
                         className="fa-icon" title={"right"}>
                        <FaAngleRight/>
                        {/*<img*/}
                        {/*    src={theme == "dark" ? "/icons8-next-dark-50.png" : "/icons8-next-light-50.png"}/>*/}
                    </div>
                </div>
            </div>
            <div className={styles['ranking-content']}>
                {ranking.map((r, index) => (
                    <div key={index} className={styles['ranking-line']}>
                        <div>
                            {index < 3 &&
                                <img className={styles["medal-icon"]} src={medals[theme][index]}/>}
                            {index >= 3 && <div className={styles["medal-number"]}>{index + 1}</div>}
                        </div>
                        <div title={r.name}>{r.first_name}</div>
                        <div>{r.count}</div>
                    </div>
                ))}
                {!isFullLoad && (
                    <div className={styles["more-button"]}>
                        <div onClick={() => setFullLoad(true)}
                             className="fa-icon" title={"load more"}>
                            <FaAngleDown/>
                            {/*<img*/}
                            {/*    src={theme == "dark" ? "/icons8-down-arrow-50-dark.png" : "/icons8-down-arrow-50-light.png"}/>*/}
                        </div>
                    </div>
                )}
                {isFullLoad && (
                    <div className={styles["more-button"]}>
                        <div onClick={() => setFullLoad(false)}
                             className="fa-icon" title={"load more"}>
                            <FaAngleUp/>
                            {/*<img*/}
                            {/*    src={theme == "dark" ? "/icons8-collapse-arrow-50-dark.png" : "/icons8-collapse-arrow-50-light.png"}/>*/}
                        </div>
                    </div>
                )}
            </div>
        </div>
    )
}


export default Ranking;
