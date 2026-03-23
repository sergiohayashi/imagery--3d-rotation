import { MsalProvider, useIsAuthenticated } from "@azure/msal-react";
import { HashRouter, BrowserRouter } from 'react-router-dom';
import { useMsal } from "@azure/msal-react";
import Login from "./components/Login/Login";
import TopMostLayout from "./components/TopMostLayout/TopMostLayout";
import {useCallback, useContext, useEffect, useState} from "react";
import axios from "axios";
import config from "./config";
import {AppContext} from "./redux/AppContext";
import {setErrorMessage, setForceLogin, setProfile} from "./redux/actions";
import Loading from "./components/Loading/Loading";
import {InteractionRequiredAuthError} from "@azure/msal-browser";

const environment = process.env.NODE_ENV || 'development';
const apiUrl = config[environment].apiUrl;


function AuthenticatedApp() {
    const { instance, accounts } = useMsal();
    const isAuthenticated = useIsAuthenticated();
    const [loginStatus, setLoginStatus] = useState("initial")    // initial, validating, error, success
    const { state, dispatch } = useContext(AppContext);
    const { isForceLogin } = state;
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        if (!instance || !accounts || accounts?.length <= 0 || isForceLogin)
            // wait initialization, or login..
            return;

        const initialize = async () => {
            try {
                const tokenSuccess = await tryAcquireToken();
                if (!tokenSuccess) {
                    dispatch(setErrorMessage('Token acquisition failed'));
                    dispatch(setForceLogin(true));
                    return;
                }
                await registerUserAsync();
            } catch (error) {
                // already handled
                console.log(error);
                // erro during initialization, go to login screen
                dispatch(setErrorMessage(error.response?.data?.message || error.message));
                dispatch(setForceLogin(true));
            }
        };

        initialize();
    }, [instance, accounts, isForceLogin, dispatch])

    useEffect(() => {
        const loadingTimeout = setTimeout(() => {
            setIsLoading(false);
        }, 2700); // Minimum loading duration of 5 seconds

        return () => clearTimeout(loadingTimeout);
    }, []);


    const registerUserAsync = async () => {
        try {
            const response = await axios.post(apiUrl + '/register', { email: accounts[0].username, name: accounts[0].name });
            dispatch(setProfile(response.data))

            // Wait for 100ms to give time for full initialization
            // await new Promise(resolve => setTimeout(resolve, 100));

            setLoginStatus("registered");
        } catch (error) {
            dispatch(setForceLogin(true));
            setLoginStatus("initial");
            dispatch(setErrorMessage(error.response?.data?.message || error.message));
        }
    }


    const tryAcquireToken = async () => {
        try {
            const tokenResponse = await instance.acquireTokenSilent({
                scopes: config["msal-scope"],
                account: accounts[0]
            });
            console.log(`token(acquireTokenSilent) acquired!`);
            return true;
        } catch (error) {
            if (error instanceof InteractionRequiredAuthError || error.errorCode === "login_required") {
                // fallback to interaction when silent call fails
                try {
                    const tokenResponse = await instance.acquireTokenRedirect({
                        scopes: config["msal-scope"],
                        account: accounts[0]
                    });
                    console.log(`token(acquireTokenRedirect) acquired!`);
                    return true;
                } catch (error) {
                    console.error('AcquireTokenRedirect error', error);
                    return false;
                }
            } else {
                console.error('acquireTokenSilent error', error);
                return false;
            }
        }
    }

    if (!instance || isLoading) {
        return <Loading/>
    } else if (accounts.length <= 0 || isForceLogin) {
        return <Login/>;
    } else {   // accounts.length> 0
        switch (loginStatus) {
            case "registered":
                return <TopMostLayout />;
            case "logged":
                return <Loading/>
                // return <Loading msg={"registering user"}/>;

            case "initial":
                return <Loading/>
                // return <Loading msg={"acquiring token"}/>;

            case "error":
                return <Login/>;
        }
    }
}

export default AuthenticatedApp;
