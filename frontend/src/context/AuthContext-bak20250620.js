// src/context/AuthContext.js

import React, {createContext, useContext, useState, useEffect, useRef} from 'react';
import { useMsal } from "@azure/msal-react";
import axios from 'axios';
import config from '../config';
import { AppContext } from '../redux/AppContext';
import {
    setErrorMessage,
    setProfile,
    // setLoggedUsing,
    // setToken,
    setCurrentChatId,
    setCurrentProject
} from '../redux/actions';

const environment = process.env.NODE_ENV || 'development';
const apiUrl = config[environment].apiUrl;

// Create the AuthContext
const AuthContext = createContext();

// status login
export const StatusLoginValues = {
    // transient login status. trigger automatic actions
    UNDEFINED: "undefined",
    LOGGED_IN_WAITING_REGISTER: "logged_in_waiting_register",

    // terminal status
    REGISTERED: "registered",
    REGISTER_FAILED: "register_failed",
    LOGGED_OUT: "logged_out",
};

export const LoggedUsingValues = {
    EMAIL: "email",
    AZURE_AD: "azure-ad",
}


const LOGIN_SCOPE = ["User.Read"];
const loginRequest = {
    scopes: LOGIN_SCOPE
};


// AuthProvider Component
export const AuthProvider = ({ children }) => {
    const { instance, inProgress, accounts } = useMsal();
    const { dispatch, state } = useContext(AppContext);

    const [statusLogin, setStatusLogin] = useState(StatusLoginValues.UNDEFINED)

    // recovered from local storage, if exists
    const [loggedUsing, setLoggedUsing] = useState(localStorage.getItem("logged-using") || null);
    const [accessTokenForEmail, setAccessTokenForEmail] = useState(localStorage.getItem('access-token-for-email') || null);

    // set after register (don't store)
    const [email, setEmail] = useState(null);
    const [name, setName] = useState(null);

    // control
    const cachedToken = useRef(null); // Ref to store the cached token
    const tokenExpirationTime = useRef(null); // Ref to store the token expiration time
    const CACHE_DURATION = 60 * 1000; // Cache duration in milliseconds (e.g., 60 seconds)
    const fetchTokenPromise = useRef(null); // Ref to store the ongoing token fetch promise


    
    // trigger actions for transient state
    useEffect(()=> {
        console.log( `===> useEffect called for status: ${statusLogin}. accounts=`, accounts);
        switch(statusLogin) {
            case StatusLoginValues.UNDEFINED: //=> check if is logged
                // undefined => logged_in
                if (is_logged_in()) {
                    console.log( "[login] Logged status detected! Change to LOGGED_IN_WAITING_REGISTER");
                    setStatusLogin(StatusLoginValues.LOGGED_IN_WAITING_REGISTER);
                } else {
                    console.log( "[login] Not logged. Set to LOGGED_OUT");
                    setStatusLogin(StatusLoginValues.LOGGED_OUT);
                }
                break;

            case StatusLoginValues.LOGGED_IN_WAITING_REGISTER:  //=>loading
                // logged_in => trigger register
                do_register2()
                    .then((email) => {
                        console.log( "[register] go_register returned with success!")
                        if (email) {
                            setStatusLogin(StatusLoginValues.REGISTERED);
                        } else {
                            console.log( "[register] need to wait more. Will be trigerred with changes in instance or accounts");
                        }
                    })
                    .catch(reason => {
                        console.log( "[register] go_register returned with error, but don't change statys!", reason);
                        dispatch(setErrorMessage(reason?.message));
                        setStatusLogin(StatusLoginValues.REGISTER_FAILED);
                    })
                break;

            case StatusLoginValues.LOGGED_OUT: //=>login
                // undefined => logged_in
                if (is_logged_in()) {
                    console.log( "[login] Logged status detected! Change to LOGGED_IN_WAITING_REGISTER");
                    setStatusLogin(StatusLoginValues.LOGGED_IN_WAITING_REGISTER);
                }
                break;
            case StatusLoginValues.REGISTERED: //=> AuthenticatedApp
                if (!is_logged_in()) {
                    setStatusLogin(StatusLoginValues.LOGGED_OUT);
                }
                break;
            case StatusLoginValues.REGISTER_FAILED: //=> login screen
                break;

        }
    }, [statusLogin, instance, accounts, accessTokenForEmail, loggedUsing])

    // persist actions
    useEffect(() => {
        localStorage.setItem('logged-using', loggedUsing);
    }, [loggedUsing]);

    // persist actions
    useEffect(() => {
        localStorage.setItem('access-token-for-email', accessTokenForEmail);
    }, [accessTokenForEmail]);


    const is_logged_in = ()=> {
        switch (loggedUsing) {
            case LoggedUsingValues.AZURE_AD:
                return (instance && accounts.length > 0)
            case LoggedUsingValues.EMAIL:
                return (!!accessTokenForEmail)
        }
    }


    const do_register2 = async () => {
        if (loggedUsing === LoggedUsingValues.EMAIL) {
            console.log("tryCheckIn(email): email mode");
            if (!accessTokenForEmail) {
                throw new Error("token is empty");
            }
            console.log( '[register] call /register-from-token-for-email >>>');
            const response = await axios.post(apiUrl + '/register-from-token-for-email', { token: accessTokenForEmail });
            console.log( '[register] call /register-from-token-for-email <<<', response);
            dispatch(setProfile(response.data));
            setEmail(response.data?.email);
            setName(response.data?.name);
            console.error("tryRegister(email) success!");
            return (response.data?.email);
        } else if (loggedUsing === LoggedUsingValues.AZURE_AD) {
            console.log("tryCheckIn: msal mode");
            if (!instance || !accounts || accounts.length<= 0) {
                console.log("[register] msal not initialized (need to wait?)");
                return null;
            }
            setLoggedUsing('azure-ad');
            setEmail(accounts[0].username);
            setName(accounts[0].name);
            console.log( '[register] call /register >>>');
            const response = await axios.post(apiUrl + '/register', { email: accounts[0].username, name: accounts[0].name });
            console.log( '[register] call /register <<<', response);
            dispatch(setProfile(response.data));
            return accounts[0].username;
        } else {
            throw new Error("login method not initialized");
        }
    }

    const loginByAzureAd = async () => {

        try {
            setLoggedUsing(LoggedUsingValues.AZURE_AD);
            console.log( "[msal]  call ssoSilent>>>");
            const response = await instance.ssoSilent(loginRequest);
            console.log( '[msal]  ssoClient <<< : ', response);
        } catch (error) {
            try {
                console.log( "[msal] ssoSilent failed. Try loginRedirect >>>", error);

                // Com esta chamada abaixo a aplicação termina e depois de login volta ao início.
                const response = await instance.loginRedirect(loginRequest);
                console.log( '[msal] loginRedirect response <<< : ', response);
            } catch (redirectError) {
                dispatch(setErrorMessage(redirectError.message || "SSO Login Redirect failed."));
            }
        } finally {
        }
    }

    const loginByEmail = async (email, password) => {
        try {
            setLoggedUsing(LoggedUsingValues.EMAIL);
            setStatusLogin(StatusLoginValues.IS_LOGGING);
            console.log("[login] call /login..>>>");
            const response = await axios.post(`${config.apiUrl}/login`, { email, password });
            console.log("[login] call /login..<<<", response);
            const { access_token: accessToken, profile } = response.data;
            if (!accessToken) {
                console.log("[login] call /login returned invalid token! Set as LOGGED_OUT");
                setStatusLogin(StatusLoginValues.LOGGED_OUT);
                dispatch(setErrorMessage("Login failed"));
                return;
            }
            setAccessTokenForEmail(accessToken);
            setStatusLogin(StatusLoginValues.LOGGED_IN_WAITING_REGISTER);
        } catch (error) {
            console.error('[login] Email/Password login failed:', error);
            dispatch(setErrorMessage(error.response?.data?.message || error.message || 'Email/Password login failed.'));
            setStatusLogin(StatusLoginValues.LOGGED_OUT);
        } finally {
        }
    };

    const resetLogin = () => {
        setStatusLogin(StatusLoginValues.UNDEFINED);
    }

    // Logout
    const logout = () => {
        if (loggedUsing === LoggedUsingValues.AZURE_AD) {
            instance.logout().catch(e => {
                console.error('SSO Logout failed:', e);
            });
        } else if(loggedUsing===LoggedUsingValues.EMAIL) {
            setAccessTokenForEmail(null);
        }
        setLoggedUsing(null);
        dispatch(setCurrentChatId(null));
        setStatusLogin(StatusLoginValues.LOGGED_OUT);
    };

    // Wrapper function to manage caching
    const getToken = async () => {
        if (statusLogin!==StatusLoginValues.REGISTERED) {
            console.log("getToken called before register. Ignore (need to wait)");
            return null;
        }
        // Check if a valid token is already cached
        const currentTime = Date.now();
        if (cachedToken.current && tokenExpirationTime.current && currentTime < tokenExpirationTime.current) {
            console.log("Returning cached token!");
            return cachedToken.current;
        }

        // If a token fetch is already in progress, wait for it to complete
        if (fetchTokenPromise.current) {
            console.log("Waiting for ongoing token fetch...");
            return fetchTokenPromise.current;
        }

        // Otherwise, fetch a new token and update the cache
        fetchTokenPromise.current = fetchToken()
            .then((token) => {
                if (token) {
                    cachedToken.current = token;
                    tokenExpirationTime.current = currentTime + CACHE_DURATION; // Cache for the defined duration
                    console.log("Token cached successfully!");
                }
                return token;
            })
            .catch((error) => {
                console.error("Error fetching token:", error);
                throw error;
            })
            .finally(() => {
                fetchTokenPromise.current = null; // Reset the promise after completion
            });

        return fetchTokenPromise.current;
    };

    const fetchToken = async () => {
        if (loggedUsing === LoggedUsingValues.AZURE_AD) {
            try {
                console.log( '[msal] acquireTokenSilent>>>');
                const tokenResponse = await instance.acquireTokenSilent({
                    scopes: LOGIN_SCOPE,
                    account: accounts[0],
                });
                console.log( '[msal] AcquireTokenSilent<<<', tokenResponse);
                console.log( "[msal] New token obtained successfully!", Date.now());
                return tokenResponse.accessToken
            } catch (error) {
                console.log( '[msal] acquireTokenSilent. Call acquireTokenRedirect <<<', error);
                if (error.name === "InteractionRequiredAuthError") {
                    try {
                        const tokenResponse = await instance.acquireTokenRedirect({
                            scopes: LOGIN_SCOPE,
                            account: accounts[0]
                        });
                        console.log("[msal] acquireTokenRedirect<<<", tokenResponse);
                        return tokenResponse.accessToken;
                    } catch (redirectError) {
                        console.log("[msal] acquireTokenRedirect Error <<<", redirectError);
                        setStatusLogin(StatusLoginValues.UNDEFINED);
                    }
                } else {
                    setStatusLogin(StatusLoginValues.UNDEFINED);
                }
            }
        } if (loggedUsing===LoggedUsingValues.EMAIL) {
            if (!accessTokenForEmail) {
                setStatusLogin(StatusLoginValues.UNDEFINED);
            }
            return accessTokenForEmail;
        } else {
            setStatusLogin(StatusLoginValues.UNDEFINED);
            return null;
        }
    }

    return (
        <AuthContext.Provider value={{loginByAzureAd, loginByEmail, logout, getToken, statusLogin, name, email, resetLogin}}>
            {children}
        </AuthContext.Provider>
    );
};

// Custom hook to use the AuthContext
export const useAuth = () => useContext(AuthContext);
