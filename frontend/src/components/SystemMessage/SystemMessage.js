// src/components/ContextArtifact/SystemMessage.js
import React, {useState, useEffect, useContext} from 'react';
import MaxModal from '../MaxModal/MaxModal'
// import { getApi } from '../../services/apiService';
import {AppContext} from "../../redux/AppContext";
import styles from "./SystemMessage.module.css"
import { useMsal } from "@azure/msal-react";
import {ThemeContext} from "../../redux/ThemeContext";
import { useNavigate  } from 'react-router-dom';
import SystemMessageEditor from "../SystemMessageEditor/SystemMessageEditor";
import {useApi} from "../../hooks/useApi";
import {FaPlus, FaTrashCan} from "react-icons/fa6";
import {FaAngleLeft, FaEdit} from "react-icons/fa";
import {Title} from "../Headings/Heading";


function SystemMessage() {
    const [messages, setMessages] = useState([]);
    const [selectedMessage, setSelectedMessage] = useState(null);
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

    useEffect(() => {
        fetchSystemMessages();
    }, [currentProject]);

    useEffect(() => {
        if (selectedMessage) {
            setDialogTitle( selectedMessage.title);
            setDialogText( selectedMessage.content);
        } else {
            setDialogTitle('');
            setDialogText( '');
        }
    }, [selectedMessage])

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

    const handleDelete = async (id) => {
        try {
            await api.delete(`/api/system_messages/${id}`);
            // setIsDialogOpen(false);
            await fetchSystemMessages()
        } catch (error) {
            console.error('Error deleting system message', error);
        }
    };

    const handleEdit = async (message= null) => {
        // setSelectedMessage(message);
        // setIsDialogOpen(message.id);

        navigate('/system_message_edit', message? { state: {message }}: {})
    };

    const handleCloseDialog = () => {
        setIsDialogOpen(false);
    };


    const modal = isDialogOpen && (
        <MaxModal show={isDialogOpen} handleClose={()=> {setIsDialogOpen(false)}}
        >
            <SystemMessageEditor
                messageId={selectedMessage?.id}
                callbackOnSave = {async (modified = false) => {
                    setIsDialogOpen(false);
                    if (modified) {
                        await fetchSystemMessages();
                    }
                }}
            />
        </MaxModal>)


    return (
        <div className={styles.container}>
            <div className={"title-with-back"}>
                <a onClick={() => navigate(-1)} className={"fa-icon"}>
                    <FaAngleLeft/>
                    {/*<img src={theme == "dark" ? "/icons8-previous-dark-50.png" : "/icons8-previous-light-50.png"}*/}
                    {/*     alt="back"/>*/}
                </a>
                <Title>System Messages</Title>
            </div>
            <div className="icon-button">
                <a onClick={() => {
                    handleEdit();
                }} className={"fa-icon"}>
                    <FaPlus/>
                    {/*<img src={theme == "dark" ? "/icons8-add-50-dark.png" : "/icons8-add-50-light.png"}*/}
                    {/*     alt="new system message"/>*/}
                </a>
            </div>
            <div className={styles.contextList}>
                {messages.map((message, index) => (
                    <div key={index} className={`${styles["content-content"]} list-item`}>
                        <span>{message.title}</span>
                        <div>
                            <a onClick={() => handleEdit(message)} className={"fa-icon"}>
                                <FaEdit/>
                                {/*<img src={theme == "dark" ? "/icons8-edit-50-dark.png" : "/icons8-edit-50-light.png"}*/}
                                {/*     alt="Edit"/>*/}
                            </a>
                        </div>
                        <div>
                            <a onClick={() => {
                                if (window.confirm("Delete this system message?")) {
                                    handleDelete(message.id);
                                }
                            }} className={"fa-icon"}>
                                <FaTrashCan/>
                                {/*<img*/}
                                {/*    src={theme == "dark" ? "/icons8-delete-30-dark.png" : "/icons8-delete-30-light.png"}*/}
                                {/*    alt="Delete"/>*/}
                            </a>
                        </div>
                    </div>
                ))}
            </div>
            {isDialogOpen && modal}
        </div>
    );
}

export default SystemMessage;
