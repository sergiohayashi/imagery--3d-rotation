import React, {useState, useEffect, useContext, useCallback} from 'react';
// import { getApi } from '../../services/apiService';
import MaxModal from '../MaxModal/MaxModal'
import styles from "./Project.module.css";
import { AppContext } from '../../redux/AppContext'; // import AppContext
import {setCurrentChatId, setCurrentProject, setErrorMessage, setProjectList} from "../../redux/actions";
import { useMsal } from "@azure/msal-react";
import {ThemeContext} from "../../redux/ThemeContext";
import {useNavigate} from "react-router-dom";
import Busy from "../Busy/Busy";
import {useApi} from "../../hooks/useApi";
import {useAuth} from "../../context/AuthContext";
import config from "../../config";
import {FaTrashCan} from "react-icons/fa6";
import {FaAngleLeft, FaEdit, FaFileAlt, FaDownload} from "react-icons/fa";
import {Subtitle, Title} from "../Headings/Heading";

function Project() {
    const [newProjectName, setNewProjectName] = useState('');
    const [editProjectName, setEditProjectName] = useState('');
    const [editingProject, setEditingProject] = useState(null);
    const [projectUsers, setProjectUsers] = useState([]);
    const [newUser, setNewUser] = useState({ email: '', role: '' });
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [isEditMode, setEditMode] = useState(false);
    const [isConfirmDelete, setConfirmDelete] = useState(false);
    const [confirmProjectName, setConfirmProjectName] = useState('');
    const [isDownloadModalOpen, setIsDownloadModalOpen] = useState(false);
    const [downloadingProject, setDownloadingProject] = useState(null);
    const [downloadYear, setDownloadYear] = useState('');
    const [chatCount, setChatCount] = useState(null);
    const [loadingCount, setLoadingCount] = useState(false);
    const { state, dispatch } = useContext(AppContext);
    const { projectList, currentProject } = state;
    const { theme } = useContext(ThemeContext);
    const { instance } = useMsal();
    const navigate = useNavigate();
    const [loading, setLoading] = useState(false);
    const api = useApi();
    const { getToken } = useAuth();


    const fetchProjects = async () => {
        try {
            const response = await api.get('/api/projects');
            dispatch(setProjectList(response.data));
        } catch (error) {/*error handled in apiService*/}
    };

    const fetchProjectUsers = async (projectId) => {
        try {
            const response = await api.get(`/api/projects/${projectId}/users`);
            setProjectUsers(response.data);
        } catch (error) {/*error handled in apiService*/}
    };

    const handleAddProject = async () => {
        setLoading(true);
        try {
            await api.post('/api/projects', { name: newProjectName });
            setNewProjectName('');
            await fetchProjects();
        } catch (error) {/*error handled in apiService*/}
        finally {
            setLoading(false);
        }
    };

    const handleUpdateProject = async () => {
        setLoading(true);
        try {
            await api.put(`/api/projects/${editingProject.id}`, { name: editProjectName });
            await fetchProjects();
        } catch (error) {/*error handled in apiService*/}
        finally {
            setLoading(false);
        }
    };

    const handleDeleteProject = async (projectId) => {
        setLoading(true);
        try {
            await api.delete(`/api/projects/${editingProject.id}`);
            await fetchProjects();
            await handleCloseModal();
        } catch (error) {/*error handled in apiService*/}
        finally {
            setLoading(false);
        }
    };

    const handleAddUser = async () => {
        setLoading(true);
        try {
            const response = await api.post(`/api/projects/${editingProject.id}/users`, newUser);
            setNewUser({email_list: '', role: ''});
            await fetchProjectUsers(editingProject.id);
            console.log( response);
            if (response.status!== 200) {
                dispatch(setErrorMessage(response.data))
            }
        } catch (error) {/*error handled in apiService*/}
        finally {
            setLoading(false);
        }
    };

    const handleDeleteUser = async (userId) => {
        setLoading(true);
        try {
            await api.delete(`/api/projects/${editingProject.id}/users/${userId}`);
            await fetchProjectUsers(editingProject.id);
        } catch (error) {/*error handled in apiService*/}
        finally {
            setLoading(false);
        }
    };

    const handleOpenModal = async (project, editMode) => {
        setLoading(true);
        try {
            setEditingProject(project);
            setEditProjectName(project.name);
            setConfirmDelete(false);
            setEditMode(editMode);
            await fetchProjectUsers(project.id);
            setIsModalOpen(true);
        }
        finally {
            setLoading(false);
        }
    };

    const handleCloseModal = () => {
        setIsModalOpen(false);
    };


    const buildEditModal = () => {
        return (
            <MaxModal handleClose={handleCloseModal}  show={isModalOpen} closeLabel={"Close"}>
                <div className={styles["modal-container"]}>
                    <div className={styles["modify-name-panel"]}>
                        <input
                            className = {"input"}
                            type="text"
                            value={editProjectName}
                            onChange={e => setEditProjectName(e.target.value)}
                            placeholder="Edit project name"
                        />
                        <button onClick={handleUpdateProject}  className="button">Modify name</button>
                    </div>
                    <div>
                        <button className="delete button" onClick={()=> {
                            setConfirmProjectName( '');
                            setConfirmDelete(true);
                        }}>Delete workspace</button>

                        {isConfirmDelete && (
                            <>
                                <div>Deleting this workspace will permanently remove all associated Contexts, System Messages, and Chats. To confirm, please enter the workspace name in the field below.</div>
                                <div className={styles["modify-name-panel"]}>
                                    <input type="text"
                                           className = {"input"}
                                           value = {confirmProjectName}
                                           onChange={e => setConfirmProjectName(e.target.value)}
                                    />
                                    <button className="delete button" onClick={async () => {
                                        if (confirmProjectName !== editProjectName) {
                                            alert("Project name doesn't match");
                                            return;
                                        }
                                        await handleDeleteProject();
                                    }}>Confirm Delete</button>
                                    <button onClick={() => {
                                        setConfirmDelete(false);
                                    }}  className="button">Cancel</button>
                                </div>
                            </>)}
                    </div>
                    <div className={styles["project-users-container"]}>
                        <div className={'title'}>Users</div>
                        <div className={styles["users-container"]}>
                            <div className={styles["users-container-scroll"]}>
                                {projectUsers.map(user => (
                                    <div key={user.user_id} className={`${styles["users-row"]} list-item`}>
                                        <div>{user.email}</div>
                                        <div>{user.role}</div>
                                        <div onClick={(event) => handleDeleteUser(user.user_id)}
                                             className="fa-icon delete" title={"delete"}>
                                            <FaTrashCan/>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                        <div className={styles["new-user-panel"]}>
                            <div><textarea
                                className={styles["new-user-email"]}
                                type="text"
                                value={newUser.email_list}
                                onChange={e => setNewUser({...newUser, email_list: e.target.value})}
                                placeholder="Enter new users email address. Users must be registered in the system. Registration will occur upon first login."
                            />
                            </div>
                            <div className={styles["new-user-button-panel"]}><select
                                value={newUser.role}
                                onChange={e => setNewUser({...newUser, role: e.target.value})}
                            >
                                <option value="">Select role</option>
                                <option value="admin">Admin</option>
                                <option value="contributor">Contributor</option>
                            </select>
                            <button
                                onClick={handleAddUser}
                                className="button"
                                disabled={!!!newUser.email_list || !!!newUser.role}
                            >Add User</button>
                            </div>
                        </div>
                    </div>
                </div>
            </MaxModal>
        );
    }

    const buildViewModal = () => {
        return (
            <MaxModal handleClose={handleCloseModal}  show={isModalOpen} closeLabel={"Close"}>
                <div className={styles["modal-container"]}>
                    <div>
                        Workspace Name: {editProjectName}
                    </div>
                    <div className={styles["project-users-container"]}>
                        <Title>Users</Title>
                        {projectUsers.map(user => (
                            <div key={user.user_id}>
                                {user.email} ({user.role})
                            </div>
                        ))}
                    </div>
                </div>
            </MaxModal>);
    }

    const canEdit = (project) => {
        return project.role !== "contributor";
    }

    const handleDownloadProject = (project) => {
        const currentYear = new Date().getFullYear().toString();
        setDownloadingProject(project);
        setDownloadYear(currentYear);
        setChatCount(null);
        setIsDownloadModalOpen(true);
    }

    const fetchChatCount = useCallback(async (projectId, year) => {
        if (!projectId || !year) {
            setChatCount(null);
            return;
        }
        
        setLoadingCount(true);
        try {
            const response = await api.get(`/api/projects/${projectId}/chat-count`, {
                params: { year: parseInt(year) }
            });
            setChatCount(response.data.count);
        } catch (error) {
            // Error handled in apiService
            setChatCount(null);
        } finally {
            setLoadingCount(false);
        }
    }, [api]);

    useEffect(() => {
        if (isDownloadModalOpen && downloadingProject && downloadYear) {
            fetchChatCount(downloadingProject.id, downloadYear);
        }
    }, [isDownloadModalOpen, downloadingProject?.id, downloadYear, fetchChatCount]);

    const handleCloseDownloadModal = () => {
        setIsDownloadModalOpen(false);
        setDownloadingProject(null);
        setDownloadYear('');
        setChatCount(null);
    }

    const handleDownloadConfirm = async () => {
        if (!downloadYear) {
            alert("Please enter a year");
            return;
        }
        
        setLoading(true);
        try {
            const token = await getToken();
            const url = new URL(
                `/api/projects/${downloadingProject.id}/chat-export`,
                config.apiUrl
            );
            url.searchParams.set("year", downloadYear);

            const response = await fetch(url.toString(), {
                method: "GET",
                headers: {
                    Authorization: `Bearer ${token}`,
                    Accept: "application/zip",
                },
            });

            if (!response.ok) {
                const problem = await response.json().catch(() => null);
                throw new Error(problem?.detail || "Unable to export chats.");
            }

            const blob = await response.blob();
            const downloadUrl = window.URL.createObjectURL(blob);

            const anchor = document.createElement("a");
            anchor.href = downloadUrl;

            // Try to read filename from header; fallback to a default
            const disposition = response.headers.get("Content-Disposition");
            const match = disposition?.match(/filename="?([^"]+)"?/);
            anchor.download = match?.[1] ?? `project-${downloadingProject.id}-${downloadYear}.zip`;

            document.body.appendChild(anchor);
            anchor.click();
            document.body.removeChild(anchor);
            window.URL.revokeObjectURL(downloadUrl);
            
            // Close modal after download
            handleCloseDownloadModal();
        } catch (error) {
            // Error handled in apiService
            dispatch(setErrorMessage(error));
        } finally {
            setLoading(false);
        }
    }

    const buildDownloadModal = () => {
        return (
            <MaxModal 
                handleClose={handleCloseDownloadModal} 
                show={isDownloadModalOpen} 
                closeLabel={"Cancel"}
            >
                <div className={styles["modal-container"]}>
                    <Title>Download Project</Title>
                    <div>Project: {downloadingProject?.name}</div>
                    <div className={styles["modify-name-panel"]}>
                        <label htmlFor="year-input">Year:</label>
                        <input
                            id="year-input"
                            className={`input ${styles["year-input"]}`}
                            type="number"
                            value={downloadYear}
                            onChange={e => setDownloadYear(e.target.value)}
                            placeholder="Enter year (e.g., 2024)"
                            min="1900"
                            max="2100"
                        />
                        <div>
                            {/* {loadingCount && (
                                <div>Loading chat count...</div>
                            )} */}
                            {chatCount !== null && (
                                <div>Chats found: {loadingCount ? "..." : chatCount}</div>
                            )}
                        </div>
                    </div>
                    <div className={styles["modify-name-panel"]}>
                        <button 
                            onClick={handleDownloadConfirm} 
                            className="button"
                            disabled={!downloadYear || chatCount<=0}
                        >
                            Download
                        </button>
                        <button 
                            onClick={handleCloseDownloadModal} 
                            className="button"
                        >
                            Cancel
                        </button>
                    </div>
                </div>
            </MaxModal>
        );
    }



    return  (
        <div className={styles.container}>
            <div className={"title-with-back"}>
                <a onClick={() => navigate(-1)}>
                    <FaAngleLeft className={"fa-icon"}/>
                    {/*<img src={theme == "dark" ? "/icons8-previous-dark-50.png" : "/icons8-previous-light-50.png"}*/}
                    {/*     alt="back"/>*/}
                </a>
                <Title>Workspace</Title>
            </div>
            <div className={styles["new-project-name-panel"]}>
                <input
                    className={`${styles["new-project-name-name"]} input`}
                    type="text"
                    value={newProjectName}
                    onChange={e => setNewProjectName(e.target.value)}
                    placeholder="New workspace name"
                />
                <button onClick={handleAddProject}
                        className="button"
                        disabled={!!!newProjectName}
                >Add workspace
                </button>
            </div>
            <div className={styles.projectList}>
                {projectList.map(project =>
                    <div key={project.id} className={`${styles["projectItem"]} list-item`}>
                        <span onClick={() => handleOpenModal(project, false)}>{project.name}</span>
                        {canEdit(project) && (
                            <div className={"fa-icon"}
                                onClick={() => handleOpenModal(project, true)}>
                                    <FaEdit/>
                            </div>
                        )}
                        <div className={"fa-icon"}
                            onClick={() => handleDownloadProject(project)}>
                                <FaDownload />
                        </div>

                    </div>)
                }
            </div>
            {isModalOpen && (() => {
                return isEditMode ? buildEditModal() : buildViewModal();
            })()}
            {isDownloadModalOpen && buildDownloadModal()}
            {loading && <Busy/>}
        </div>)
}

export default Project;
