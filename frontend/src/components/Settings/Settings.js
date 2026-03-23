import React, {useContext, useEffect, useState} from "react";
import styles from "./Settings.module.css"
// import { getApi } from '../../services/apiService';
import {AppContext} from "../../redux/AppContext";
import {useAccount, useMsal} from "@azure/msal-react";
import {ThemeContext} from "../../redux/ThemeContext";
import Ranking from "../Ranking/Ranking";
import {useNavigate} from "react-router-dom";
import {setDisableFromat, setInfoMessage} from "../../redux/actions";
import {useApi} from "../../hooks/useApi";
import {setErrorMessage} from "../../redux/actions";
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faEye, faEyeSlash } from '@fortawesome/free-solid-svg-icons';
import {FaAngleLeft} from "react-icons/fa";
import {SectionTitle, Title} from "../Headings/Heading";
import config from "../../config";

function Settings() {
    const { state, dispatch } = useContext(AppContext);
    const { accounts, instance} = useMsal();
    const { balance } = state;
    const account = useAccount(accounts[0] || {});
    const { theme } = useContext(ThemeContext);
    const navigate = useNavigate();
    // const { instance } = useMsal();
    // const [balance, setBalance] = useState(null);
    const api = useApi();
    const [password1, setPassword1] = useState(null);
    const [password2, setPassword2] = useState(null);
    const [isWorking, setWorking] = useState(false);
    // const {errorMessage, setErrorMessage} = useState(null);
    const [showPassword1, setShowPassword1] = useState(false);
    const [showPassword2, setShowPassword2] = useState(false);
    const [excludeNameFromRanking, setExcludeNameFromRanking] = useState(false);

    // useEffect(() => {
    //     const loadBalance = async () => {
    //         const result = await api.get("/api/account/balance");
    //         setBalance(result?.data?.balance)
    //     }
    //     loadBalance()
    // },[dispatch, instance])

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


    const handleSetPassword = async (e) => {
        e.preventDefault();
        if (password1 !== password2) {
            dispatch(setErrorMessage("password don't match"));
            return;
        }
        try {
            setWorking( true);
            const response = await api.post("/api/account/set-password", {
                password: password1
            })
            dispatch(setInfoMessage("Password updated successfully"));
        } finally {
            setWorking( false);
            setPassword1('');
            setPassword2('');
        }
    }

    const handleSwitchExcludeNameFromRanking = async () => {
        try {
            // setWorking( true);
            const response = await api.put("/api/account/exclude-from-ranking/switch")
            setExcludeNameFromRanking(response.data?.status);
        } finally {
            // setWorking(false);
        }
    }

    return (
        <div className={styles['container']}>
            <div className={"title-with-back"}>
                <a onClick={() => navigate(-1)}>
                    <FaAngleLeft className={"fa-icon"}/>
                    {/*<img src={theme == "dark" ? "/icons8-previous-dark-50.png" : "/icons8-previous-light-50.png"}*/}
                    {/*     alt="back"/>*/}
                </a>
                <Title>{account?.name}</Title>
            </div>
            <div>
                <Title>Usage</Title>
                {typeof balance?.balance === 'number' && <div>Your current month estimate cost is <span
                    className={styles["balance"]}>${Math.trunc(balance.balance * 100) / 100}</span> ({balance.count} requests)</div>}
            </div>
            {/*<div>*/}
            {/*    <Title>Settings</Title>*/}
            {/*    <div className={"row-center"}>*/}
            {/*        <input type="checkbox"*/}
            {/*            checked={excludeNameFromRanking}*/}
            {/*            onChange={(e)=> {*/}
            {/*                handleSwitchExcludeNameFromRanking()*/}
            {/*            }}*/}
            {/*        />Exclude my name from the usage ranking list*/}
            {/*    </div>*/}
            {/*</div>*/}
            {/*<hr/>*/}
            {/*{!config.is_partner && (*/}
            {/*<div>*/}
            {/*    <Title>Update or set a password</Title>*/}
            {/*    <div>* Password for logging in via username/password. It is not the password for your company account.</div>*/}
            {/*    <div  className={styles["password-update-form"]}>*/}
            {/*        <div className={styles["form-group"]}>*/}
            {/*            <div>Password:</div>*/}
            {/*            <div className={styles["password-input-container"]}>*/}
            {/*                <input*/}
            {/*                    type={showPassword1 ? "text" : "password"}*/}
            {/*                    // placeholder="Password"*/}
            {/*                    value={password1}*/}
            {/*                    onChange={(e) => setPassword1(e.target.value)}*/}
            {/*                    required*/}
            {/*                />*/}
            {/*                <div*/}
            {/*                    // type="button"*/}
            {/*                    onClick={() => setShowPassword1(!showPassword1)} // Toggle visibility*/}
            {/*                    className={"fa-icon"}*/}
            {/*                >*/}
            {/*                    <FontAwesomeIcon icon={showPassword1 ? faEyeSlash : faEye}/>*/}
            {/*                </div>*/}
            {/*            </div>*/}
            {/*        </div>*/}
            {/*        <div className={styles["form-group"]}>*/}
            {/*            <div>Repeat password:</div>*/}
            {/*            <div className={styles["password-input-container"]}>*/}
            {/*                <input*/}
            {/*                    type={showPassword2 ? "text" : "password"}*/}
            {/*                    // placeholder="Password"*/}
            {/*                    value={password2}*/}
            {/*                    onChange={(e) => setPassword2(e.target.value)}*/}
            {/*                    required*/}
            {/*                />*/}
            {/*                <div*/}
            {/*                    // type="button"*/}
            {/*                    onClick={() => setShowPassword2(!showPassword2)} // Toggle visibility*/}
            {/*                    className={"fa-icon"}*/}
            {/*                >*/}
            {/*                    <FontAwesomeIcon icon={showPassword2 ? faEyeSlash : faEye}*/}
            {/*                                     />*/}
            {/*                </div>*/}
            {/*            </div>*/}
            {/*        </div>*/}
            {/*        <button type="submit" className={`${styles["submit-btn"]} button`} disabled={isWorking}*/}
            {/*            onClick={handleSetPassword}*/}
            {/*        >*/}
            {/*            {isWorking ? 'Working...' : 'Update'}*/}
            {/*        </button>*/}
            {/*    </div>*/}
            {/*</div>)}*/}
        </div>
    )
}


export default Settings;
