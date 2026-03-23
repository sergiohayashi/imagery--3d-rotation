import React, {useEffect, useState} from 'react';
import AppRouter from './components/AppRouter/AppRouter';
//Important! I need to use HashRouter instead of BrowserRouter because of an error in nginx.
import { HashRouter as Router, Routes, Route } from 'react-router-dom';
// import Login from './components/Login/Login'
import { useStore } from './redux/Store';
import { AppContext } from './redux/AppContext';
import './App.css';
import TopMostLayout from "./components/TopMostLayout/TopMostLayout";
import { MsalProvider } from "@azure/msal-react";
// import ReactDOM from "react-dom/client";
import ErrorMessage from "./components/ErrorMessage/ErrorMessage";
import InfoMessage from "./components/InfoMessage/InfoMessage";

import {ThemeProvider} from './redux/ThemeProvider'
import SharedChat from "./components/Chat/SharedChat";
import {AuthProvider} from "./context/AuthContext";

function getObjectFromLocalStorage(name, _default) {
    const json = localStorage.getItem(name)
    try {
        return json ? JSON.parse(json) : _default
    } catch (error) {
        return _default;
    }
}

function App() {

    // const initialState = {}
    const initialState = {
        currentProject: { id: "68d0617c5f83766eeb6abb15", name: "default" },   //use fixed
        errorMessage: null,
        projectList: getObjectFromLocalStorage('projectList', []),
        modelList: [],
        isLoading: false,
        account: null,
        showNav: !window.matchMedia("(max-width: 768px)").matches,
        isMobile: window.matchMedia("(max-width: 768px)").matches,
        chatSlidingWindow: false,
        useAgent: null,
        useModel: localStorage.getItem('model') || null,
        useModelAlternatives: getObjectFromLocalStorage('modelAlternatives', []),
        isDisableFormat: (localStorage.getItem('isDisableFormat') || "false") === 'true',
        showOnTop: localStorage.getItem('showOnTop')==null?0:parseInt(localStorage.getItem('showOnTop')),
        chatId: null,
        chatLayout: localStorage.getItem('layout') || "bottom",
        isCodeEditor: (localStorage.getItem('isCodeEditor') || "false") === 'true',
        showMultiColumn: true,
        preferences: getObjectFromLocalStorage('preferences', {}),
        currentFileContext: getObjectFromLocalStorage('currentFileContext', null),

    };
    if (!['bottom', 'side'].includes(initialState.chatLayout)) {
        initialState.chatLayout = 'bottom';
    }
    const [state, dispatch] = useStore(initialState);
    // const [state, dispatch] = useStore();

    return (
          <AppContext.Provider value={{ state, dispatch }}>
              {/* <MsalProvider instance={msalInstance}> */}
                  <AuthProvider> {/* Wrap with AuthProvider */}
                      <ThemeProvider>

                      {/*<div style={{float:"right", bottom: "5px", right: "5px", color: '#80808061', fontFamily: "monospace"}}>*/}
                      {/*    v.2023/10/06 20:05</div>*/}
                      <ErrorMessage />
                      <InfoMessage />
                      {/* <div>App.js here!</div> */}
                      <Router>
                          <Routes>
                              <Route path="/shared/:guid" element={<SharedChat />} />
                              <Route path="/*" element={<TopMostLayout />} />
                          </Routes>
                      </Router>
                      </ThemeProvider>
                  </AuthProvider>
              {/* </MsalProvider> */}
          </AppContext.Provider>
    );
}


export default App;

