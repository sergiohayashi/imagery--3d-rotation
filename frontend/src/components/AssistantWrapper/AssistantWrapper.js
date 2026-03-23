import styles from "./AssistantWrapper.module.css"
import React, {useContext, useState} from "react";
// import {getApi} from "../../services/apiService";
import {setInfoMessage} from "../../redux/actions";
import Busy from "../Busy/Busy";
import {useMsal} from "@azure/msal-react";
import {ThemeContext} from "../../redux/ThemeContext";
import {AppContext} from "../../redux/AppContext";
import {useApi} from "../../hooks/useApi";
import {FaTrashCan, FaWandMagicSparkles} from "react-icons/fa6";
import {FaRegCheckCircle, FaRegTimesCircle} from "react-icons/fa";
import {GrUndo} from "react-icons/gr";
import {LuUndo2} from "react-icons/lu";

function AssistantWrapper({ children, notifyImprovedText, message, type="text"}) {
    const [improvedCandidate, setImprovedCandidate] = useState()
    const [undoText, setUndoText] = useState();
    const [current, setCurrent] = useState();
    const { theme, switchTheme } = useContext(ThemeContext);
    const { state, dispatch } = useContext(AppContext);
    const { instance, accounts, inProgress } = useMsal();
    const [loading, setLoading] = useState(false);
    const api = useApi();

    const handleRequestImprovement = async() => {
        const current = message
        try {
            setLoading(true)
            const response = await api.post('/api/llm_task/improve-my-text',
                {
                    text: current,
                    type: type
                }
            );
            setImprovedCandidate(response.data);
            setCurrent(current);
        } finally {{
            setLoading(false);
        }}
    }


    const improvedCandidateDiv = improvedCandidate && (
        <div className={styles['candidate-window']}>
            <div className={`${styles['candidate-output-container']} code-view`}>
                {improvedCandidate}
            </div>
            <div className={styles['candidate-panel']}>
                <div
                        className={"fa-icon -larger-xx"}
                        onClick={(event) => {
                            setImprovedCandidate(null)
                        }}
                        title={"Reject"}
                >
                    <FaRegTimesCircle/>
                    {/*<img*/}
                    {/*    src={theme == "dark" ? "/icons8-cancel-50-dark.png" : "/icons8-cancel-50-light.png"}*/}
                    {/*/>*/}
                </div>
                <div
                        className={"fa-icon -larger-xx -accept"}
                        onClick={(event) => {
                            setUndoText(current);
                            notifyImprovedText(improvedCandidate);
                            setImprovedCandidate(null)
                        }}
                        title={"Accept and replace the current prompt"}
                >
                    <FaRegCheckCircle/>
                    {/*<img*/}
                    {/*    src={theme == "dark" ? "/icons8-accept-50-green-dark.png" : "/icons8-accept-50-blue-light.png"}*/}
                    {/*/>*/}
                </div>
            </div>
        </div>
    )

    return (
        <>
            <div className={styles["assistant-wrapper"]}>
                <div className={styles['assistant-panel']}>
                    {undoText && <div
                        className={"fa-icon"}
                        onClick={() => {
                            notifyImprovedText(undoText);
                            setUndoText(null);
                        }}>
                        <LuUndo2/>
                        {/*<img*/}
                        {/*    src={theme == "dark" ? "/icons8-undo-50--dark.png" : "/icons8-undo-50--light.png"}*/}
                        {/*/>*/}
                    </div>}
                    <div onClick={() => handleRequestImprovement()} className={"fa-icon"}>
                        <FaWandMagicSparkles/>
                        {/*<img*/}
                        {/*    src={theme == "dark" ? "/icons8-magic-wand-dark.png" : "/icons8-magic-wand-light.png"}*/}
                        {/*/>*/}
                    </div>
                </div>
            </div>
            {loading && <Busy/>}
            {improvedCandidateDiv}
        </>
    );
};

export default AssistantWrapper;

