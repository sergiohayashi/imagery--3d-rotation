import styles from "./ExternalUserImagery.module.css"
import React, {useContext, useEffect, useState} from "react";
import {useNavigate} from "react-router-dom";
import {ThemeContext} from "../../redux/ThemeContext";
import {AppContext} from "../../redux/AppContext";
import {useMsal} from "@azure/msal-react";
// import { getApi } from '../../services/apiService';
// import ContextModal from "../ContextModal/ContextModal";
// import {formatDateMonthDay} from "../../helpers/formatters";
import {useApi} from "../../hooks/useApi";
import {FontAwesomeIcon} from "@fortawesome/react-fontawesome";
import {faEye, faEyeSlash} from "@fortawesome/free-solid-svg-icons";
import {setErrorMessage, setInfoMessage} from "../../redux/actions";
import {Title} from "../Headings/Heading";

function ExternalUserImagery() {
    const { theme } = useContext(ThemeContext);
    const navigate = useNavigate();
    const { state, dispatch } = useContext(AppContext);
    const { instance } = useMsal();
    const api = useApi();
    const [password1, setPassword1] = useState(null);
    const [password2, setPassword2] = useState(null);
    const [name, setName] = useState(null);
    const [email, setEmail] = useState(null);
    const [isWorking, setWorking] = useState(false);
    // const {errorMessage, setErrorMessage} = useState(null);
    const [showPassword1, setShowPassword1] = useState(false);
    const [showPassword2, setShowPassword2] = useState(false);
    const [users, setUsers] = useState([]);


    useEffect(() => {
        fetchUsers();
    }, []);
    //
    const fetchUsers = async () => {
        try {
            const response = await api.get('/api/manager/ext-users');
            setUsers(response.data);
        } catch (error) {
            console.error("Error fetching users:", error);
        }
    };

    // const formatDate = (date) => {
    //     if (!date) return null;
    //     const year = date.getFullYear();
    //     const month = String(date.getMonth() + 1).padStart(2, '0'); // Months are zero-based
    //     const day = String(date.getDate()).padStart(2, '0');
    //
    //     return `${month}-${day}`;
    // };
    //
    // const [isCommentModalOpen, setCommentModalOpen]=  useState(false);
    // const [commentFeedbackId, setCommentFeedbackId] = useState(null);
    // const [commentText, setCommentText] = useState('');


    const handleAddUser= async (id, comment) => {
        // e.preventDefault();
        if (password1 !== password2) {
            dispatch(setErrorMessage("password don't match"));
            return;
        }
        try {
            setWorking(true);
            const response = await api.post("/api/manager/ext-users", {
                name,
                email,
                password: password1
            })
            dispatch(setInfoMessage("User added successfully"));
            setEmail('');
            setName('');
            setPassword1('');
            setPassword2('');
            await fetchUsers();
        } catch(error) {
        } finally {
            setWorking( false);
            setPassword1('');
            setPassword2('');
        }

        // await api.post(`/api/manager/feedback/${id}/comment`, {
        //     text: comment
        // });
        // await fetchFeedback()
    }


    return (
        <div>
            <Title>Add external user</Title>
            <div className={styles["password-update-form"]}>
                <div className={styles["form-group"]}>
                    <div>Name:</div>
                    <div className={styles["password-input-container"]}>
                        <input
                            type={"text"}
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                            required
                        />
                    </div>
                </div>
                <div className={styles["form-group"]}>
                    <div>Email:</div>
                    <div className={styles["password-input-container"]}>
                        <input
                            type={"email"}
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            required
                        />
                    </div>
                </div>
                <div className={styles["form-group"]}>
                    <div>Password:</div>
                    <div className={styles["password-input-container"]}>
                        <input
                            type={showPassword1 ? "text" : "password"}
                            value={password1}
                            onChange={(e) => setPassword1(e.target.value)}
                            required
                        />
                        <button
                            type="button"
                            onClick={() => setShowPassword1(!showPassword1)} // Toggle visibility
                            className={styles["toggle-password-btn"]}
                        >
                            <FontAwesomeIcon icon={showPassword1 ? faEyeSlash : faEye} className={styles["icons"]}/>
                        </button>
                    </div>
                </div>
                <div className={styles["form-group"]}>
                    <div>Repeat password:</div>
                    <div className={styles["password-input-container"]}>
                        <input
                            type={showPassword2 ? "text" : "password"}
                            value={password2}
                            onChange={(e) => setPassword2(e.target.value)}
                            required
                        />
                        <button
                            type="button"
                            onClick={() => setShowPassword2(!showPassword2)} // Toggle visibility
                            className={styles["toggle-password-btn"]}
                        >
                            <FontAwesomeIcon icon={showPassword2 ? faEyeSlash : faEye}
                                             className={styles["icons"]}/>
                        </button>
                    </div>
                </div>
                <button type="submit" className={`${styles["submit-btn"]} button`} disabled={isWorking}
                        onClick={handleAddUser}
                >
                    {isWorking ? 'Working...' : 'Add user'}
                </button>
                <hr/>
                <div className={styles.projectList}>
                    {users.map((user,idx) =>
                        <div key={idx} className={`${styles["projectItem"]} list-item`}>
                            <div>{user.name}</div>
                            <div>{user.email}</div>
                        </div>)
                    }
                </div>

            </div>
        </div>
    );
}


export default ExternalUserImagery;
