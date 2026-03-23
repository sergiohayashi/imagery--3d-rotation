import React, {useContext, useEffect, useRef, useState} from 'react';
import styles from './Login.module.css';
import config from "../../config";
import {setRetryLogin, setForceLogin, setErrorMessage} from "../../redux/actions";
import {AppContext} from "../../redux/AppContext";
import { useMsal } from "@azure/msal-react";
import {StatusLoginValues, useAuth} from '../../context/AuthContext';
import Loading from "../Loading/Loading";
import Busy from "../Busy/Busy";
import {Title} from "../Headings/Heading";

function Login() {
    const { state, dispatch } = useContext(AppContext);
    const { instance } = useMsal();

    const { loginByAzureAd, loginByEmail, statusLogin } = useAuth();
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [busy, setBusy] = useState(false);

    useEffect(() => {
        if (statusLogin === StatusLoginValues.LOGGED_OUT &&
            localStorage.getItem('logged-using') === 'azure-ad') {
            loginByAzureAd();           // this runs ssoSilent first
        }
    }, [statusLogin]);


    const handleLoginByAzureAd = async (e) => {
        e.preventDefault();
        await loginByAzureAd();
    };

    const handleLoginByEmail = async (e) => {
        e.preventDefault();
        await loginByEmail(email, password);
    };
    //
    // if (statusLogin === StatusLoginValues.LOGGED_IN_WAITING_REGISTER || statusLogin === StatusLoginValues.REGISTERING) {
    //     return (<div className={styles["loading"]}><Loading/></div>)
    // }
    return (
        <div className={styles["login-container"]}>
            <div className={styles['title']}>
                <Title>Imagery {config.is_partner && "- for Partner"}</Title>
                <br/>
                <img
                    src={"/android-chrome-512x512.png"}
                    alt="App Logo"
                    className={styles["app-logo"]}
                />

            </div>

            <div className={styles["login-form"]}>
                <div className={styles["login-group"]}>
                    <button onClick={handleLoginByAzureAd} className={`${styles["submit-btn"]} button`}>
                        Log in with Microsoft Account
                    </button>
                </div>
                <div className={styles["separator"]}>
                    <span>or</span>
                </div>
                <div className={styles["login-group"]}>
                    <div >
                        <div className={styles["form-group"]}>
                            <input
                                type="email"
                                placeholder="Email"
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                required
                            />
                        </div>
                        <div className={styles["form-group"]}>
                            <input
                                type="password"
                                placeholder="Password"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                required
                            />
                        </div>
                        <button type="submit" className={`${styles["submit-btn"]} button`}
                                onClick={handleLoginByEmail}
                        >
                            {'Login'}
                        </button>
                    </div>
                </div>
            </div>
            {busy && <Busy/>}
        </div>
    );
}

export default Login;
