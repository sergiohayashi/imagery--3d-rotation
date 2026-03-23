import React, {useContext, useEffect, useState} from 'react';
import { Route, Routes, useNavigate } from 'react-router-dom';
import Chat from '../Chat/Chat';
import ContextArtifact from '../ContextArtifact/ContextArtifact';
import ChatHistory from '../ChatHistory/ChatHistory'
import SystemMessage from '../SystemMessage/SystemMessage';
import {
    setCurrentChatId,
    setShowNav,
    setIsMobile,
    setCurrentProject,
    setResizeDetected,
    setCurrentFileContext
} from "../../redux/actions";
import styles from './AppRouter.module.css'
import {AppContext} from "../../redux/AppContext";
// import { useMsal, useAccount } from "@azure/msal-react";
import ContextModal from "../ContextModal/ContextModal";
import SystemMessageEditorPage from "../SystemMessageEditorPage/SystemMessageEditorPage";
// import {useApi} from "../../hooks/useApi";
import {FaEdit, FaPlusCircle} from "react-icons/fa";
import {GoTriangleDown} from "react-icons/go";
import HomeInProject from "./HomeInProject";
import {FaBars} from "react-icons/fa6";
import Files from "../Files/Files";
import {useApi} from "../../hooks/useApi";
import FileContextTop from "../FileContextTop/FileContextTop";


function AppRouter() {
    const { state, dispatch } = useContext(AppContext);
    const { projectList, currentProject, showNav, isMobile, currentFileContext, showFilesNav, temporaryChat } = state;
    // const [fileContextList, setFileContextList] = useState([]);
    // const { accounts} = useMsal();
    // const account = useAccount(accounts[0] || {});
    const navigate = useNavigate();
    const api = useApi();

    useEffect(() => {
        const mediaQueryList = window.matchMedia("(max-width: 768px)");
        const documentChangeHandler = () => {
            // console.log( 'window size Modified! match = ', mediaQueryList.matches)
            dispatch(setShowNav(!mediaQueryList.matches));
            dispatch(setIsMobile(mediaQueryList.matches));
        }

        // Add listener
        mediaQueryList.addEventListener("change", documentChangeHandler);

        // Cleanup function
        return () => {
            // Remove listener
            mediaQueryList.removeEventListener("change", documentChangeHandler);
        }
    }, []); // Empty dependency array means this effect runs once on mount and cleanup on unmount


    useEffect(() => {
        const handleResize = () => {
            // Get the current window dimensions
            const width = window.innerWidth;
            const height = window.innerHeight;

            // Determine if the current width qualifies as mobile
            const isMobile = width < 768;
            dispatch(setResizeDetected({ width, height, isMobile }));
        };

        // Add the resize event listener
        window.addEventListener('resize', handleResize);

        // Optionally, trigger the handler on mount to initialize the state properly
        handleResize();

        // Clean up the event listener on component unmount
        return () => {
            window.removeEventListener('resize', handleResize);
        };
    }, [dispatch]);

    // const loadFileContextList = async () => {
    //     try {
    //         console.log( 'calling  /file_context...');
    //         const result = await api.get('/api/file_context', {
    //             params: {
    //                 project_id: currentProject.id,
    //             }
    //         })
    //         console.log('file_context:' , JSON.stringify(result));
    //         setFileContextList([{
    //             id: null,
    //             title: "(no context)"
    //         }, ...result.data]);
    //         dispatch(setCurrentFileContext(null));
    //     } catch (error) {
    //         console.log( 'Error: ', error);
    //
    //     }
    //     console.log( 'calling  /file_context... DONE');
    // }



    // const [showProjectSwitch, setShowProjectSwitch]= useState(null);
    // const [showFileContextSwitch, setShowFileContextSwitch]= useState(null);
    // const projectSwitchModal = !!showProjectSwitch && (
    //     <ContextModal
    //         clickPosition ={showProjectSwitch}
    //         handleClose={() => setShowProjectSwitch(null)} closeLabel={"Close"}>
    //         <div className={styles["title-with-icon"]}>
    //             <div className="fa-icon"
    //                 onClick={() => {
    //                     navigate('/workspace')
    //                 }}>
    //                     <FaEdit/>
    //             </div>
    //         </div>
    //         <div className={styles["modal-list-container-scroll"]}>
    //             {(projectList || []).map((d, index) => (
    //                 <div className={"selection-list-item"} key={index} onClick={() => {
    //                     dispatch(setCurrentProject(d));
    //                     dispatch(setCurrentChatId(null));
    //                     setShowProjectSwitch(null);
    //                 }}>
    //                     <div className={styles['modal-list-title']}>{d.name}</div>
    //                 </div>
    //             ))}
    //         </div>
    //     </ContextModal>
    // )

    // useEffect(() => {
    //     if (currentProject) {
    //         loadFileContextList();
    //     }
    // }, [currentProject]);

    const leftNav = (
        <div className={styles["nav-top-container"]}>
            <div className={styles["tab-nav-project-parent"]}>
                {isMobile && <div className={"fa-icon -larger"} onClick={() => dispatch(setShowNav(!showNav))}>
                    <FaBars/>
                </div>
                }
                {/* <div className={styles["tab-nav-project"]} onClick={(e) => {
                    const rect = e.target.getBoundingClientRect();
                    setShowProjectSwitch({top:rect.top, left:rect.left});
                }}>
                    {currentProject?.name}
                    <GoTriangleDown size={20}/>
                </div> */}
            </div>
            <div className={styles["tab-nav-middle"]}>
                <ChatHistory/>
            </div>
        </div>
    )

    return (
        <>
            {/* <div>AppRouter.js here!</div> */}
            {(showNav && !temporaryChat) && isMobile &&
                <div className={styles["left-container-overlay"]} onClick={() => dispatch(setShowNav(false))}></div>}
            <div
                className={`${styles["left-container-top"]} ${(showNav && !temporaryChat) ? styles["sidebar-visible"] : styles["sidebar-hidden"]}`}
            >
                {leftNav}
            </div>
            <div className={styles["right-container-top"]}>
                <Routes className={styles["tab-routes"]}>
                    {currentProject && (
                        <>
                            <Route path="/chat/:chatIdFromUrl" element={<Chat/>}/>
                            <Route path="/context_artifact" element={<ContextArtifact/>}/>
                            <Route path="/system_message" element={<SystemMessage/>}/>
                            <Route path="/system_message_edit" element={<SystemMessageEditorPage/>}/>
                            <Route path="/files" element={<Files/>}/>
                            {/*<Route path="/file-context" element={<FileContextTop/>}/>*/}
                        </>
                    )}
                    <Route path="*" element={<HomeInProject/>}/>
                </Routes>
            </div>
            {/*<div className={`${styles['right-most-files-nav']} ${showFilesNav? styles["files-nav-visible"]:styles["files-nav-hidden"]}`}>*/}
            {/*   <FileContextTop/>*/}
            {/*</div>*/}
            {/* {projectSwitchModal} */}
        </>
    );
}

export default AppRouter;

