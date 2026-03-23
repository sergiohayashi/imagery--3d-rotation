// import { PublicClientApplication } from '@azure/msal-browser';
// import config from "../config";
//
// const environment = process.env.NODE_ENV || 'development';
//
// //TODO: Move to common location
// const msalConfig = {
//     auth: {
//         clientId: '4609c939-f740-4f31-8e61-9d5405037924', // Your client id
//         authority: 'https://login.microsoftonline.com/63b19fa5-5c31-448f-9fae-b391edb09eab',
//         redirectUri: '/#/home', //config[environment].frontendUrl,
//     },
//     cache: {
//         cacheLocation: 'localStorage', // This configures where your cache will be stored
//         storeAuthStateInCookie: false, // Set this to "true" if you are having issues on IE11 or Edge
//     }
// };
// console.log( 'create msalInstance object');
// export const msalInstance = new PublicClientApplication(msalConfig);
// // export const myMSALObj = new msal.UserAgentApplication(msalConfig);
//
