import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './App';
import reportWebVitals from './reportWebVitals';

import { PublicClientApplication } from '@azure/msal-browser';

const msalConfig = {
    auth: process.env?.REACT_APP_VERSION === 'partner'? {
        clientId: 'bf2aa0ff-6b48-4ff7-8834-a626a15bcf02',
        authority: 'https://login.microsoftonline.com/organizations',
        redirectUri: '/',
    }:{
        clientId: '4609c939-f740-4f31-8e61-9d5405037924',
        authority: 'https://login.microsoftonline.com/63b19fa5-5c31-448f-9fae-b391edb09eab',
        redirectUri: '/',
    },
    cache: {
        cacheLocation: 'localStorage', // This configures where your cache will be stored
        storeAuthStateInCookie: false, // Set this to "true" if you are having issues on IE11 or Edge
    }
};
window._msalConfig = msalConfig;
const msalInstance = new PublicClientApplication(msalConfig);
msalInstance.initialize().finally(() => {
    const root = ReactDOM.createRoot(document.getElementById("root"));
    root.render(
        <React.StrictMode>
            <App/>
        </React.StrictMode>
    );
});

// await msalInstance.initialize();
// const root = ReactDOM.createRoot(document.getElementById('root'));
// root.render(
//     <React.StrictMode>
//         <App msalInstance={msalInstance}/>
//     </React.StrictMode>
// );

// If you want to start measuring performance in your app, pass a function
// to log results (for example: reportWebVitals(console.log))
// or send to an analytics endpoint. Learn more: https://bit.ly/CRA-vitals
reportWebVitals();
