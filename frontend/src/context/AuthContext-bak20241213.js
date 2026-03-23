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

// AuthProvider Component
export const AuthProvider = ({ children }) => {
    const { instance, accounts } = useMsal();
    const { dispatch, state } = useContext(AppContext);
    const { loggedUsing } = state;
    const [isRegistering, setIsRegistering] = useState(false); // To handle initial loading
    const [email, setEmail] = useState(null);
    const [name, setName] = useState(null);
    const cachedToken = useRef(null); // Ref to store the cached token
    const tokenExpirationTime = useRef(null); // Ref to store the token expiration time
    const CACHE_DURATION = 60 * 1000; // Cache duration in milliseconds (e.g., 60 seconds)
    const isExecutingRegister = useRef(false); // Flag to track if the function is already running
    const registerPromise = useRef(null); // Promise to serialize calls

    useEffect(() => {
        // console.log( 'CALL tryRecoverToken!');
        tryRegister().then(r => console.log("register done!"));
    }, [loggedUsing, accounts, instance]);

    const checkIn = async () => {
        await tryRegister();
    }

    //TODO: O correto é implementar como status, ou variável global!
    const isLoggedIn = () => {
        if (loggedUsing === 'email') {
            return !!localStorage.getItem('access-token-for-email');
        } else if (loggedUsing === 'azure-ad') {
            return accounts.length > 0;
        } else {
            return false;
        }
    }

    //TODO: O correto é implementar como status, ou variável global!
    const isRegistered = () => {
        console.log('isRegistered. name: ', name);
        return !!name;
    }

    const tryRegister = async () => {
        if (isRegistered()) {
            console.log( "tryRegister: Already registered.");
            return;
        }

        counter += 1;
        console.log( "** tryRegister ** called! Should be called only once!", counter);
        if (isExecutingRegister.current) {
            // If already running, return the existing promise
            console.log("tryRegister: Return recoverTokenPromise");
            return registerPromise.current;
        }

        // Set the flag and create a new promise
        isExecutingRegister.current = true;
        console.log("tryRegister: No recoverTokenPromise. Get New!", Date.now());
        registerPromise.current = (async () => {
            if (loggedUsing === 'email') {
                console.log("tryCheckIn(email): email mode");
                const _token = localStorage.getItem('access-token-for-email');
                if (!_token) {
                    return;
                }
                try {
                    setIsRegistering(true);
                    const response = await axios.post(apiUrl + '/register-from-token-for-email', { token: _token });
                    dispatch(setProfile(response.data));
                    setEmail(response.data?.email);
                    setName(response.data?.name);
                    console.error("tryRegister(email) success!");
                } catch (error) {
                    console.error("tryRegister(email) failed! Force logout", error);
                    // dispatch(setErrorMessage(error.message || "Register failed."));
                    resetLogin();
                } finally {
                    setIsRegistering(false);
                }
            } else if (instance && accounts && accounts.length > 0) {
                console.log("tryCheckIn: msal mode");
                if (!accounts || accounts.length<= 0) {
                    return;
                }
                try {
                    setIsRegistering(true);
                    dispatch(setLoggedUsing('azure-ad'));
                    setEmail(accounts[0].username);
                    setName(accounts[0].name);
                    const response = await axios.post(apiUrl + '/register', { email: accounts[0].username, name: accounts[0].name });
                    dispatch(setProfile(response.data));
                    console.log("tryRegister (msal): success!");
                } catch (error) {
                    console.error("tryRegister (msal): failed! force Logout:", error);
                    resetLogin();
                } finally {
                    setIsRegistering(false);
                }
            } else {
                setIsRegistering(false);
            }
        })();

        // Once the promise resolves, reset the flag and promise
        registerPromise.current.finally(() => {
            isExecutingRegister.current = false;
            registerPromise.current = null;
        });
        return registerPromise.current;
    };


    // Refresh Token
    const refreshToken = async () => {
        if (loggedUsing === 'azure-ad' && instance && accounts && accounts.length > 0) {
            try {
                const tokenResponse = await instance.acquireTokenSilent({
                    scopes: ["User.Read"],
                    account: accounts[0]
                });
                // dispatch(setToken(tokenResponse.accessToken));
                return tokenResponse.accessToken;
            } catch (error) {
                console.error("Token refresh failed:", error);
                if (error.name === "InteractionRequiredAuthError") {
                    try {
                        const tokenResponse = await instance.acquireTokenRedirect({
                            scopes: ["User.Read"],
                            account: accounts[0]
                        });
                        // dispatch(setToken(tokenResponse.accessToken));
                        return tokenResponse.accessToken;
                    } catch (redirectError) {
                        console.error("Token refresh via redirect failed:", redirectError);
                        // dispatch(setErrorMessage(redirectError.message || "Token refresh failed."));
                        resetLogin();
                    }
                } else {
                    // dispatch(setErrorMessage(error.message || "Token refresh failed."));
                    resetLogin();
                }
            }
        } else {
            console.warn("Refresh token is not applicable for email login.");
        }
    };



    const loginByAzureAd = async () => {
        const loginRequest = {
            scopes: ["User.Read"] // Adjust scopes as needed
        };
        try {
            setIsRegistering(true);
            const response = await instance.ssoSilent(loginRequest);
            dispatch(setLoggedUsing('azure-ad'));
            await checkIn();
        } catch (error) {
            try {
                await instance.loginRedirect(loginRequest);
                await checkIn();
            } catch (redirectError) {
                dispatch(setErrorMessage(redirectError.message || "SSO Login Redirect failed."));
            }
        } finally {
            setIsRegistering(false);
        }
    }

    const loginByEmail = async (email, password) => {
        try {
            setIsRegistering(true);
            const response = await axios.post(`${config.apiUrl}/login`, { email, password });
            const { access_token: accessToken, profile } = response.data;
            if (!accessToken) {
                dispatch(setErrorMessage("Invalid token"));
                return;
            }

            localStorage.setItem('access-token-for-email', accessToken);
            localStorage.setItem('logged-using', "email");
            dispatch(setLoggedUsing("email"));
            await checkIn();

        } catch (error) {
            console.error('Email/Password login failed:', error);
            dispatch(setErrorMessage(error.response?.data?.message || error.message || 'Email/Password login failed.'));
        } finally {
            setIsRegistering(false);
        }
    };

    // Logout
    const logout = () => {
        console.log( "logout called!");
        localStorage.removeItem('access-token-for-email');
        localStorage.removeItem('logged-using');
        // dispatch(setToken(null));
        dispatch(setCurrentChatId(null));
        // dispatch(setCurrentProject(null));
        if (loggedUsing === 'azure-ad') {
            instance.logout().catch(e => {
                console.error('SSO Logout failed:', e);
            });
        }
        setLoggedUsing(null);
    };


    const fetchTokenPromise = useRef(null); // Ref to store the ongoing token fetch promise

    // Wrapper function to manage caching
    const getToken = async () => {
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
        console.log( "fetchToken() called!", loggedUsing);
        if (loggedUsing === 'azure-ad') {
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
                        resetLogin();
                    }
                } else {
                    resetLogin();
                }
            }
        } else {  //user/password
            let token = localStorage.getItem('access-token-for-email')
            if (!token) {
                resetLogin();
            }
            return token
        }
    }

    const resetLogin = async () => {
        console.log( "resetLogin called!");
        localStorage.removeItem('access-token-for-email');
        localStorage.removeItem('logged-using');
        // dispatch(setToken(null));
        dispatch(setCurrentChatId(null));
        // dispatch(setCurrentProject(null));
        // if (loggedUsing === 'azure-ad') {
        //     instance.logout().catch(e => {
        //         console.error('SSO Logout failed:', e);
        //     });
        // }
        setLoggedUsing(null);
    }

    return (
        <AuthContext.Provider value={{ authMethod: loggedUsing, loginByAzureAd, loginByEmail, logout, getToken, isLoggedIn, isRegistering, name, email, refreshToken, isRegistered }}>
            {children}
        </AuthContext.Provider>
    );
};

// Custom hook to use the AuthContext
export const useAuth = () => useContext(AuthContext);
