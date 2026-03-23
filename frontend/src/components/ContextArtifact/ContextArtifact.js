// src/components/ContextArtifact/ContextArtifact.js
import React, {useState, useEffect, useContext} from 'react';
import MaxModal from '../MaxModal/MaxModal'
// import { getApi } from '../../services/apiService';
import {AppContext} from "../../redux/AppContext";
import styles from "./ContextArtifact.module.css"
import { useMsal } from "@azure/msal-react";
import {ThemeContext} from "../../redux/ThemeContext";
import { useNavigate  } from 'react-router-dom';
import Busy from "../Busy/Busy";
import {useApi} from "../../hooks/useApi";
import {FaPlus, FaTrashCan} from "react-icons/fa6";
import {FaAngleLeft, FaEdit} from "react-icons/fa";
import {Title} from "../Headings/Heading";

function ContextArtifact() {
    const [artifacts, setArtifacts] = useState([]);
    const [selectedArtifact, setSelectedArtifact] = useState(null);
    const [dialogText, setDialogText] = useState('');
    const [dialogTitle, setDialogTitle] = useState('');
    const [isDialogOpen, setIsDialogOpen] = useState(false);
    const { state, dispatch } = useContext(AppContext);
    const { currentProject } = state;
    const { instance } = useMsal();
    const { theme } = useContext(ThemeContext);
    const navigate = useNavigate();
    const [loading, setLoading] = useState(false);

    const api = useApi();

    useEffect(() => {
        (async  ()=> {
            await fetchArtifacts();
        })();
    }, [currentProject]);

    useEffect(() => {
        if (selectedArtifact) {
            setDialogTitle( selectedArtifact.title);
            setDialogText( selectedArtifact.content);
        } else {
            setDialogTitle('');
            setDialogText( '');
        }
    }, [selectedArtifact])

    const fetchArtifacts = async () => {
        // try {
        //     const response = await api.get('/api/context_artifacts', {
        //         params: {
        //             project_id: currentProject.id
        //         }
        //     });
        //     setArtifacts(response.data);
        // } catch (error) {
        //     /* error handled in apiService */
        // }
    };

    const handleCreate = async () => {
        try {
            const response = await api.post('/api/context_artifacts',
                { type: 'context', content: dialogText, title: dialogTitle, project: currentProject.id }
            );
            setArtifacts([...artifacts, response.data]);
            setSelectedArtifact(null);
            setIsDialogOpen(false);
            await fetchArtifacts()
        } catch (error) {
            /* error handled in apiService */
        }
    };

    const handleUpdate = async () => {
        setLoading(true);
        try {
            await api.put(`/api/context_artifacts/${selectedArtifact.id}`,
                { type: 'context', content: dialogText, title: dialogTitle, project: currentProject.id }
            );
            setSelectedArtifact(null);
            setIsDialogOpen(false);
            await fetchArtifacts()
        } catch (error) {
            /* error handled in apiService */
        }
        finally {
            setLoading(false);
        }
    };


    const handleDelete = async (id) => {
        setLoading(true);
        try {
            await api.delete(`/api/context_artifacts/${id}`);
            // setIsDialogOpen(false);
            await fetchArtifacts()
        } catch (error) {
            /* error handled in apiService */
        }
        finally {
            setLoading(false);
        }
    };

    const handleEdit = async (artifact) => {
        setLoading(true);
        try {
            const response = await api.get(`/api/context_artifacts/${artifact.id}`)
            setSelectedArtifact( response.data);
            setIsDialogOpen(true);
        } catch (error) {
            /* error handled in apiService */
        }
        finally {
            setLoading(false);
        }
    };

    const handleCloseDialog = () => {
        setIsDialogOpen(false);
    };

    const modal = (
        <MaxModal show={isDialogOpen} handleClose={handleCloseDialog}>
            <div className={styles["modal-container"]}>
                Name: <input type={"text"}
                              className = {`${styles['content-title-input']} input`}
                              value={dialogTitle}
                              onChange = {e=> setDialogTitle( e.target.value)}
                              placeholder={"Input the content title"}/>
                <textarea
                    autoFocus
                    rows={4}
                    value={dialogText}
                    className={`code ${styles["content-dialog"]}`}
                    onChange={e => setDialogText(e.target.value)}
                    placeholder={"Input the content"}/>
                <div className={"button-panel"}>
                    {/*{selectedArtifact?.id && <button className="delete button" onClick={() => handleDelete(selectedArtifact.id)} >Delete</button>}*/}
                    <button className="button" onClick={selectedArtifact?.id ? handleUpdate : handleCreate} >Save</button>
                </div>
            </div>
        </MaxModal>
    )

    return (
        <div className={styles.container}>
            <div className={"title-with-back"}>
                <a onClick={() => navigate(-1)} className={"fa-icon"}>
                    <FaAngleLeft/>
                    {/*<img src={theme == "dark" ? "/icons8-previous-dark-50.png" : "/icons8-previous-light-50.png"}*/}
                    {/*     alt="back"/>*/}
                </a>
                <Title>Predefined Context</Title>
            </div>
            <div className="fa-icon"
                onClick={(event) => {
                    setSelectedArtifact({
                        title: '',
                        content: '',
                        id: null
                    });
                    setIsDialogOpen(true);
                }}>
                    <FaPlus/>
                    {/*<img src={theme == "dark" ? "/icons8-add-50-dark.png" : "/icons8-add-50-light.png"}*/}
                    {/*     alt="new context"/>*/}
                {/*</a>*/}
            </div>
            <div className={styles.contextList}>
                {artifacts.map((artifact, index) => (
                    <div key={index} className={`${styles["contentItem"]} list-item`}>
                        <span>{artifact.title}</span>
                        <div className="fa-icon"
                            onClick={() => handleEdit(artifact)}>
                                <FaEdit/>
                                {/*<img src={theme == "dark" ? "/icons8-edit-50-dark.png" : "/icons8-edit-50-light.png"}*/}
                                {/*     alt="Edit"/>*/}
                        </div>
                        <div className="fa-icon"
                            onClick={() => {
                                if (window.confirm("Delete this content?")) {
                                    handleDelete(artifact.id);
                                }
                            }}>
                                <FaTrashCan/>
                                {/*<img*/}
                                {/*    src={theme == "dark" ? "/icons8-delete-30-dark.png" : "/icons8-delete-30-light.png"}*/}
                                {/*    alt="Delete"/>*/}
                            {/*<a onClick={() => handleEdit(message)}>Edit</a>*/}
                        </div>
                    </div>
                ))}
            </div>
            {modal}
            {loading && <Busy/>}
        </div>
    );
}

export default ContextArtifact;
