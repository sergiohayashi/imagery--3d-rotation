// src/context/AuthContext.js

import React, {createContext, useContext, useState, useEffect, useRef} from 'react';
import { useMsal } from "@azure/msal-react";
import axios from 'axios';
import config from '../config';
import { AppContext } from '../redux/AppContext';
import {
    setErrorMessage,
    setProfile,
    setLoggedUsing,
    // setToken,
    setCurrentChatId,
    setCurrentProject
} from '../redux/actions';

const environment = process.env.NODE_ENV || 'development';
const apiUrl = config[environment].apiUrl;

// Create the AuthContext
const AuthContext = createContext();

let counter = 0;


// status login
const StatusLoginValues = {
    UNDEFINED: "undefined",
    LOGGED_IN: "logged_in",
    LOGGED_OUT: "logged_out",
    REGISTERING: "registering",
    REGISTERED: "registered",
    REGISTER_FAILED: "register_failed",
    TOKEN_FAILED: "token_failed",
};

const LoggedUsingValues = {
    EMAIL: "email",
    AZURE_AD: "azure-ad",
}

// AuthProvider Component
export const AuthProviderNew = ({ children }) => {
    const { instance, accounts } = useMsal();
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
    const isExecutingRegister = useRef(false); // Flag to track if the function is already running
    const registerPromise = useRef(null); // Promise to serialize calls

    // on first loading. Try to register, if logged in
    useEffect(()=> {
        const isLoggedIn = ()=> {
            switch (loggedUsing) {
                case LoggedUsingValues.AZURE_AD:
                    return (instance || accounts.length > 0)
                case LoggedUsingValues.EMAIL:
                    return (!!accessTokenForEmail)
            }
        }

        switch(statusLogin) {
            case StatusLoginValues.UNDEFINED: //=>login
                // undefined => logged_in
                if (isLoggedIn()) {
                    setStatusLogin(StatusLoginValues.LOGGED_IN);
                }
                break;

            case StatusLoginValues.LOGGED_IN:  //=>loading
                // logged_in => registered or registered_failed
                tryRegister()
                    .then(value => {
                        if (!!name && !!email) {
                            setStatusLogin(StatusLoginValues.REGISTERED);
                        } else {
                            setStatusLogin(StatusLoginValues.REGISTER_FAILED);
                        }
                    })
                    .catch(reason => {
                        setStatusLogin(StatusLoginValues.REGISTER_FAILED);
                    })
                    .finally(() => {})
                break;

            case StatusLoginValues.LOGGED_OUT: //=>login
                if (isLoggedIn()) {
                    setStatusLogin(StatusLoginValues.LOGGED_IN);
                }
                break;

            case StatusLoginValues.REGISTERED: //=> AuthenticatedApp
                break;
            case StatusLoginValues.REGISTERING: //=> loading screen
                break;
            case StatusLoginValues.REGISTER_FAILED: //=> login screen
                break;
            case StatusLoginValues.TOKEN_FAILED:  //=> login screen
                break;

        }
    }, [statusLogin, loggedUsing, accounts, instance, name])

    useEffect(() => {
        localStorage.setItem('logged-using', loggedUsing);
    }, [loggedUsing]);

    useEffect(() => {
        localStorage.setItem('access-token-for-email', accessTokenForEmail);
    }, [accessTokenForEmail]);


    const tryRegister = async () => {
        if (isExecutingRegister.current) {
            // If already running, return the existing promise
            console.log("tryRegister: Return recoverTokenPromise");
            return registerPromise.current;
        }

        // Set the flag and create a new promise
        isExecutingRegister.current = true;
        console.log("tryRegister: No recoverTokenPromise. Get New!", Date.now());

        registerPromise.current = (async () => {
            if (loggedUsing === LoggedUsingValues.EMAIL) {
                console.log("tryCheckIn(email): email mode");
                if (!accessTokenForEmail) {
                    return;
                }
                const response = await axios.post(apiUrl + '/register-from-token-for-email', { token: accessTokenForEmail });
                dispatch(setProfile(response.data));
                setEmail(response.data?.email);
                setName(response.data?.name);
                console.error("tryRegister(email) success!");
            } else if (loggedUsing === LoggedUsingValues.AZURE_AD) {
                console.log("tryCheckIn: msal mode");
                if (!instance || !accounts || accounts.length<= 0) {
                    return;
                }
                dispatch(setLoggedUsing('azure-ad'));
                setEmail(accounts[0].username);
                setName(accounts[0].name);
                const response = await axios.post(apiUrl + '/register', { email: accounts[0].username, name: accounts[0].name });
                dispatch(setProfile(response.data));
            }
        })();

        // Once the promise resolves, reset the flag and promise
        registerPromise.current.finally(() => {
            isExecutingRegister.current = false;
            registerPromise.current = null;
        });
        return registerPromise.current;
    };

    const loginByAzureAd = async () => {
        const loginRequest = {
            scopes: ["User.Read"] // Adjust scopes as needed
        };
        try {
            const response = await instance.ssoSilent(loginRequest);
            setLoggedUsing(LoggedUsingValues.AZURE_AD);
        } catch (error) {
            try {
                await instance.loginRedirect(loginRequest);
            } catch (redirectError) {
                dispatch(setErrorMessage(redirectError.message || "SSO Login Redirect failed."));
            }
        }
    }

    const loginByEmail = async (email, password) => {
        try {
            const response = await axios.post(`${config.apiUrl}/login`, { email, password });
            const { access_token: accessToken, profile } = response.data;
            if (!accessToken) {
                dispatch(setErrorMessage("Login failed"));
                return;
            }
            localStorage.setItem('access-token-for-email', accessToken);
            setLoggedUsing(LoggedUsingValues.EMAIL);
        } catch (error) {
            console.error('Email/Password login failed:', error);
            dispatch(setErrorMessage(error.response?.data?.message || error.message || 'Email/Password login failed.'));
        }
    };

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
            // console.log("Returning cached token!");
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
        if (statusLogin!==StatusLoginValues.REGISTERED) {
            console.log("fetchToken called before register. Ignore (need to wait)");
            return null;
        }
        if (loggedUsing === LoggedUsingValues.AZURE_AD) {
            try {
                console.log( 'Acquire new token using acquireTokenSilent!');
                const tokenResponse = await instance.acquireTokenSilent({
                    scopes: ["User.Read"],
                    account: accounts[0],
                });
                console.log( "New token obtained successfully!", Date.now());
                return tokenResponse.accessToken
            } catch (error) {
                if (error.name === "InteractionRequiredAuthError") {
                    try {
                        const tokenResponse = await instance.acquireTokenRedirect({
                            scopes: ["User.Read"],
                            account: accounts[0]
                        });
                        return tokenResponse.accessToken;
                    } catch (redirectError) {
                        console.error("Token refresh via redirect failed:", redirectError);
                        setStatusLogin(StatusLoginValues.TOKEN_FAILED);
                    }
                } else {
                    setStatusLogin(StatusLoginValues.TOKEN_FAILED);
                }
            }
        } if (loggedUsing===LoggedUsingValues.EMAIL) {
            if (!accessTokenForEmail) {
                setStatusLogin(StatusLoginValues.TOKEN_FAILED);
            }
            return accessTokenForEmail;
        } else {
            return null;
        }
    }


    return (
        <AuthContext.Provider value={{loginByAzureAd, loginByEmail, logout, getToken, statusLogin, name, email}}>
            {children}
        </AuthContext.Provider>
    );
};

// Custom hook to use the AuthContext
export const useAuth = () => useContext(AuthContext);
