// src/components/ContextArtifact/SystemMessage.js
import React, {useState, useEffect, useContext} from 'react';
import MaxModal from '../MaxModal/MaxModal'
// import { getApi } from '../../services/apiService';
import {AppContext} from "../../redux/AppContext";
import styles from "./SystemMessageEditorPage.module.css"
import { useMsal } from "@azure/msal-react";
import {ThemeContext} from "../../redux/ThemeContext";
import {useLocation, useNavigate} from 'react-router-dom';
import SystemMessageEditor from "../SystemMessageEditor/SystemMessageEditor";
import {useApi} from "../../hooks/useApi";
import {FaAngleLeft} from "react-icons/fa";
import {Title} from "../Headings/Heading";


function SystemMessageEditorPage() {
    const location = useLocation();
    const { message } = location.state || {}; //


    const [messages, setMessages] = useState([]);
    // const [message, setmessage] = useState(null);
    const [dialogText, setDialogText] = useState('');
    const [dialogTitle, setDialogTitle] = useState('');
    const [isDialogOpen, setIsDialogOpen] = useState(false);
    const { state, dispatch } = useContext(AppContext);
    const { currentProject } = state;
    const { instance } = useMsal();
    const { theme } = useContext(ThemeContext);
    const navigate = useNavigate();
    const [isSystemMessageDialogShared, setSystemMessageDialogShared] = useState(false)
    const api = useApi();

    // useEffect(() => {
    //     fetchSystemMessages();
    // }, [currentProject]);
    //
    // useEffect(() => {
    //     if (message) {
    //         setDialogTitle( message.title);
    //         setDialogText( message.content);
    //     } else {
    //         setDialogTitle('');
    //         setDialogText( '');
    //     }
    // }, [message])
    //
    const fetchSystemMessages = async () => {
        try {
            const response = await api.get('/api/system_messages', {
                params: {
                    project_id: currentProject.id
                }
            });
            setMessages(response.data);
        } catch (error) {
            console.error('Error fetching system messages', error);
        }
    };

    return (
        <div className={styles.container}>
            <div className={`title-with-back`}>
                <a onClick={() => navigate(-1)} className={"fa-icon"}>
                    <FaAngleLeft/>
                    {/*<img src={theme == "dark" ? "/icons8-previous-dark-50.png" : "/icons8-previous-light-50.png"}*/}
                    {/*     alt="back"/>*/}
                </a>
                <Title>System Message Editor</Title>
            </div>
            <SystemMessageEditor
                messageId={message?.id}
                callbackOnSave = {async (modified = false) => {
                    // setIsDialogOpen(false);
                    if (modified) {
                        await fetchSystemMessages();
                    }
                }}
            />
        </div>
    );
}

export default SystemMessageEditorPage;
