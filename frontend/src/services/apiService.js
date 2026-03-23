// import config from "../config";
// import axios from 'axios';
// import { setErrorMessage, setForceLogin } from "../redux/actions";
// import { InteractionRequiredAuthError } from "@azure/msal-browser";
//
// const acquireToken = async (dispatch, msalInstance, scopes, account) => {
//     try {
//         const tokenResponse = await msalInstance.acquireTokenSilent({
//             scopes,
//             account
//         });
//         return tokenResponse.accessToken;
//     } catch (error) {
//         if (error instanceof InteractionRequiredAuthError || error.errorCode === "login_required") {
//             try {
//                 const tokenResponse = await msalInstance.acquireTokenRedirect({
//                     scopes,
//                     account
//                 });
//                 return tokenResponse.accessToken;
//             } catch (innerError) {
//                 console.error('Error during acquireTokenRedirect:', innerError);
//                 dispatch(setForceLogin(true));
//                 throw innerError;
//             }
//         } else {
//             console.error('Error during acquireTokenSilent:', error);
//             dispatch(setForceLogin(true));
//             throw error;
//         }
//     }
// };
//
// export const getApi = (dispatch, msalInstance) => {
//     const environment = process.env.NODE_ENV || 'development';
//     const apiUrl = config[environment].apiUrl;
//
//     const api = axios.create({
//         baseURL: apiUrl,
//     });
//
//     api.interceptors.request.use(async (config) => {
//         const accounts = msalInstance.getAllAccounts();
//         if (accounts.length <= 0) {
//             console.log('No account found. Redirecting to login.');
//             dispatch(setForceLogin(true));
//             return config;
//         }
//
//         try {
//             const token = await acquireToken(dispatch, msalInstance, config["msal-scope"], accounts[0]);
//             config.headers.Authorization = `Bearer ${token}`;
//             return config;
//         } catch (error) {
//             console.error('Error acquiring token:', error);
//             return config;
//         }
//
//     });
//
//     api.interceptors.response.use(
//         response => response,
//         error => {
//             if (error.response?.data?.detail) {
//                 try {
//                     dispatch(setErrorMessage(error.response.data.detail.map(item => item.msg).join(",")));
//                 } catch (ignore) {
//                     dispatch(setErrorMessage(error.response.data.detail));
//                 }
//             } else if (error.response?.data) {
//                 dispatch(setErrorMessage(error.response.data));
//             } else {
//                 dispatch(setErrorMessage(error.response?.data?.message || error.message));
//             }
//
//             if (error.response && (error.response.status === 401 || error.response.status === 403)) {
//                 dispatch(setForceLogin(true));
//             }
//
//             return Promise.reject(error);
//         }
//     );
//
//     return api;
// };
//
// export const getToken = async (dispatch, msalInstance) => {
//     const accounts = msalInstance.getAllAccounts();
//     if (accounts.length <= 0) {
//         console.log('No account found. Redirecting to login.');
//         dispatch(setForceLogin(true));
//         return null;
//     }
//
//     try {
//         const token = await acquireToken(dispatch, msalInstance, config["msal-scope"], accounts[0]);
//         return token;
//     } catch (error) {
//         console.error('Error acquiring token:', error);
//         return null;
//     }
//
// };
