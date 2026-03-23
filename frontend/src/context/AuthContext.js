import React, {createContext, useContext, useState, useEffect, useRef} from 'react';
import { useMsal } from "@azure/msal-react";
import axios from 'axios';
import config from '../config';
import { AppContext } from '../redux/AppContext';
import {
    setErrorMessage,
    setProfile,
    setCurrentChatId,
} from '../redux/actions';
import {InteractionStatus} from "@azure/msal-browser";

// const environment = process.env.NODE_ENV || 'development';
const apiUrl = config.apiUrl;

// Create the AuthContext
const AuthContext = createContext();

// status login
export const StatusLoginValues = {
    // // New state to wait for MSAL initialization
    // INITIALIZING: "initializing",

    // // transient login status. trigger automatic actions
    // UNDEFINED: "undefined",
    // LOGGED_IN_WAITING_REGISTER: "logged_in_waiting_register",

    // // terminal status
    REGISTERED: "registered",
    // REGISTER_FAILED: "register_failed",
    // LOGGED_OUT: "logged_out",
};

export const LoggedUsingValues = {
    // EMAIL: "email",
    // AZURE_AD: "azure-ad",
}


const LOGIN_SCOPE = ["User.Read"];
const loginRequest = {
    scopes: LOGIN_SCOPE
};


export const AuthProvider = ({ children }) => {
    // const { instance, inProgress, accounts } = useMsal();
    // const { dispatch } = useContext(AppContext);
    const [statusLogin, setStatusLogin] = useState(StatusLoginValues.REGISTERED);
    // const [statusLogin, setStatusLogin] = useState(null);

    // recovered from local storage, if exists
    // const [loggedUsing, setLoggedUsing] = useState(localStorage.getItem("logged-using") || null);
    // const [accessTokenForEmail, setAccessTokenForEmail] = useState(localStorage.getItem('access-token-for-email') || null);

    // set after register (don't store)
    const [email, setEmail] = useState(null);
    const [name, setName] = useState(null);

    // control
    // const cachedToken = useRef(null); // Ref to store the cached token
    // const tokenExpirationTime = useRef(null); // Ref to store the token expiration time
    // const CACHE_DURATION = 60 * 1000; // Cache duration in milliseconds (e.g., 60 seconds)
    // const fetchTokenPromise = useRef(null); // Ref to store the ongoing token fetch promise


    // const triedSilentSso = useRef(false);

    // useEffect(() => {
    //     if (statusLogin !== StatusLoginValues.LOGGED_OUT) return;
    //     if (inProgress !== InteractionStatus.None) return;
    //     if (triedSilentSso.current) return;
    //
    //     // Only try silent SSO if we don't know the method or we last used Azure AD
    //     if (!loggedUsing || loggedUsing === LoggedUsingValues.AZURE_AD) {
    //         console.log('ONE MORE CHECK...');
    //         triedSilentSso.current = true;
    //         if (instance && accounts.length > 0) {
    //             setLoggedUsing(LoggedUsingValues.AZURE_AD);
    //             instance.setActiveAccount(accounts[0]);
    //             setStatusLogin(StatusLoginValues.LOGGED_IN_WAITING_REGISTER);
    //         }
    //     }
    // }, [statusLogin, inProgress, instance, loggedUsing]);


    // 1. Handle redirect and MSAL events once
    // useEffect(() => {
    //     const cb = (e) => {
    //         if (e.eventType === "msal:login_success") {
    //             instance.setActiveAccount(e.payload.account);
    //         }
    //     };
    //     const listenerId = instance.addEventCallback(cb);

    //     return () => instance.removeEventCallback(listenerId);
    // }, [instance]);


    // trigger actions for transient state


    // persist actions
    // persist actions


    // const is_logged_in = ()=> {
    //     switch (loggedUsing) {
    //         case LoggedUsingValues.AZURE_AD:
    //             return (instance && accounts.length > 0)
    //         case LoggedUsingValues.EMAIL:
    //             return (!!accessTokenForEmail)
    //     }
    // }


    const do_register2 = async () => {
        // if (loggedUsing === LoggedUsingValues.EMAIL) {
        //     console.log("tryCheckIn(email): email mode");
        //     if (!accessTokenForEmail) {
        //         throw new Error("token is empty");
        //     }
        //     console.log( '[register] call /register-from-token-for-email >>>');
        //     const response = await axios.post(apiUrl + '/register-from-token-for-email', { token: accessTokenForEmail });
        //     console.log( '[register] call /register-from-token-for-email <<<', response);
        //     dispatch(setProfile(response.data));
        //     setEmail(response.data?.email);
        //     setName(response.data?.name);
        //     console.error("tryRegister(email) success!");
        //     return (response.data?.email);
        // } else if (loggedUsing === LoggedUsingValues.AZURE_AD) {
        //     console.log("tryCheckIn: msal mode");
        //     if (!instance || !accounts || accounts.length<= 0) {
        //         console.log("[register] msal not initialized (need to wait?)");
        //         return null;
        //     }
        //     setLoggedUsing('azure-ad');
        //     setEmail(accounts[0].username);
        //     setName(accounts[0].name);
        //     console.log( '[register] call /register >>>');
        //     const response = await axios.post(apiUrl + '/register', {
        //         email: accounts[0].username,
        //         name: accounts[0].name,
        //         tenant_id: accounts[0].tenantId
        //     });
        //     console.log( '[register] call /register <<<', response);
        //     dispatch(setProfile(response.data));
        //     return accounts[0].username;
        // } else {
        //     throw new Error("login method not initialized");
        // }
    }

    const loginByAzureAd = async () => {

        // try {
        //     console.log( 'selected loginByAzureAd');
        //     if (loggedUsing!== LoggedUsingValues.AZURE_AD) setLoggedUsing(LoggedUsingValues.AZURE_AD);
        //     console.log( "[msal]  call ssoSilent>>>");
        //     const response = await instance.ssoSilent(loginRequest);
        //     console.log( '[msal]  ssoClient <<< : ', response);
        // } catch (error) {
        //     try {
        //         console.log( "[msal] ssoSilent failed. Try loginRedirect >>>", error);

        //         // Com esta chamada abaixo a aplicação termina e depois de login volta ao início.
        //         const response = await instance.loginRedirect(loginRequest);
        //         console.log( '[msal] loginRedirect response <<< : ', response);
        //     } catch (redirectError) {
        //         dispatch(setErrorMessage(redirectError.message || "SSO Login Redirect failed."));
        //     }
        // } finally {
        // }
    }

    const loginByEmail = async (email, password) => {
        // try {
        //     console.log( 'selected loginByEmail');
        //     if (loggedUsing!== LoggedUsingValues.EMAIL) setLoggedUsing(LoggedUsingValues.EMAIL);
        //     // setStatusLogin(StatusLoginValues.IS_LOGGING);
        //     console.log("[login] call /login..>>>");
        //     const response = await axios.post(`${config.apiUrl}/login`, { email, password });
        //     // const response = await axios.post(apiUrl + '/register', { email: accounts[0].username, name: accounts[0].name, tenant_id: accounts[0].tenantId});
        //     // const response = await axios.post(`${config.apiUrl}/login`, { email, password });
        //     console.log("[login] call /login..<<<", response);
        //     const { access_token: accessToken } = response.data;
        //     if (!accessToken) {
        //         console.log("[login] call /login returned invalid token! Set as LOGGED_OUT");
        //         setStatusLogin(StatusLoginValues.LOGGED_OUT);
        //         dispatch(setErrorMessage("Login failed"));
        //         return;
        //     }
        //     setAccessTokenForEmail(accessToken);
        //     setStatusLogin(StatusLoginValues.LOGGED_IN_WAITING_REGISTER);
        // } catch (error) {
        //     console.error('[login] Email/Password login failed:', error);
        //     dispatch(setErrorMessage(error.response?.data?.message || error.message || 'Email/Password login failed.'));
        //     setStatusLogin(StatusLoginValues.LOGGED_OUT);
        // } finally {
        // }
    };

    const resetLogin = () => {
        // setStatusLogin(StatusLoginValues.UNDEFINED);
    }

    // Logout
    const logout = () => {
        // if (loggedUsing === LoggedUsingValues.AZURE_AD) {
        //     instance.logout().catch(e => {
        //         console.error('SSO Logout failed:', e);
        //     });
        // } else if(loggedUsing===LoggedUsingValues.EMAIL) {
        //     setAccessTokenForEmail(null);
        //     localStorage.removeItem('access-token-for-email'); // Also remove from storage
        // }
        // setStatusLogin(StatusLoginValues.LOGGED_OUT);
        // setLoggedUsing(null);
        // localStorage.removeItem('logged-using'); // Also remove from storage
        // dispatch(setCurrentChatId(null));
    };

    // Wrapper function to manage caching
    const getToken = async () => {
        return null;
        // if (statusLogin!==StatusLoginValues.REGISTERED) {
        //     console.log("getToken called before register. Ignore (need to wait)");
        //     return null;
        // }
        // // Check if a valid token is already cached
        // const currentTime = Date.now();
        // if (cachedToken.current && tokenExpirationTime.current && currentTime < tokenExpirationTime.current) {
        //     // console.log("Returning cached token!");
        //     return cachedToken.current;
        // }

        // // If a token fetch is already in progress, wait for it to complete
        // if (fetchTokenPromise.current) {
        //     console.log("Waiting for ongoing token fetch...");
        //     return fetchTokenPromise.current;
        // }

        // // Otherwise, fetch a new token and update the cache
        // fetchTokenPromise.current = fetchToken()
        //     .then((token) => {
        //         if (token) {
        //             cachedToken.current = token;
        //             tokenExpirationTime.current = currentTime + CACHE_DURATION; // Cache for the defined duration
        //             // console.log("Token cached successfully!");
        //         }
        //         return token;
        //     })
        //     .catch((error) => {
        //         console.error("Error fetching token:", error);
        //         throw error;
        //     })
        //     .finally(() => {
        //         fetchTokenPromise.current = null; // Reset the promise after completion
        //     });

        // return fetchTokenPromise.current;
    };

    const fetchToken = async () => {
        // if (loggedUsing === LoggedUsingValues.AZURE_AD) {
        //     try {
        //         console.log( '[msal] acquireTokenSilent>>>');
        //         const tokenResponse = await instance.acquireTokenSilent({
        //             scopes: LOGIN_SCOPE,
        //             account: accounts[0],
        //         });
        //         // console.log( '[msal] AcquireTokenSilent<<<', tokenResponse);
        //         // console.log( "[msal] New token obtained successfully!", Date.now());
        //         return tokenResponse.accessToken
        //     } catch (error) {
        //         console.log( '[msal] acquireTokenSilent. Call acquireTokenRedirect <<<', error);
        //         if (error.name === "InteractionRequiredAuthError") {
        //             try {
        //                 const tokenResponse = await instance.acquireTokenRedirect({
        //                     scopes: LOGIN_SCOPE,
        //                     account: accounts[0]
        //                 });
        //                 // console.log("[msal] acquireTokenRedirect<<<", tokenResponse);
        //                 return tokenResponse.accessToken;
        //             } catch (redirectError) {
        //                 console.log("[msal] acquireTokenRedirect Error <<<", redirectError);
        //                 setStatusLogin(StatusLoginValues.UNDEFINED);
        //             }
        //         } else {
        //             setStatusLogin(StatusLoginValues.UNDEFINED);
        //         }
        //     }
        // } if (loggedUsing===LoggedUsingValues.EMAIL) {
        //     if (!accessTokenForEmail) {
        //         setStatusLogin(StatusLoginValues.UNDEFINED);
        //     }
        //     return accessTokenForEmail;
        // } else {
        //     setStatusLogin(StatusLoginValues.UNDEFINED);
        //     return null;
        // }
    }

    return (
        <AuthContext.Provider value={{loginByAzureAd, loginByEmail, logout, getToken, statusLogin, name, email, resetLogin}}>
            {children}
        </AuthContext.Provider>
    );
};

// Custom hook to use the AuthContext
export const useAuth = () => useContext(AuthContext);
