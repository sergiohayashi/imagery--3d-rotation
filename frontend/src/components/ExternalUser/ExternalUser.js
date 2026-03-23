import styles from "./ExternalUser.module.css"
import React, {useContext, useEffect, useState} from "react";
import {useNavigate} from "react-router-dom";
import {ThemeContext} from "../../redux/ThemeContext";
import {AppContext} from "../../redux/AppContext";
import {useMsal} from "@azure/msal-react";
//import { getApi } from '../../services/apiService';
//import ContextModal from "../ContextModal/ContextModal";
import {formatDateMonthDay} from "../../helpers/formatters";
import {useApi} from "../../hooks/useApi";
import {FontAwesomeIcon} from "@fortawesome/react-fontawesome";
import {faEye, faEyeSlash} from "@fortawesome/free-solid-svg-icons";
import {setErrorMessage, setInfoMessage} from "../../redux/actions";
import {Title} from "../Headings/Heading";
import {FaTrashCan} from "react-icons/fa6";

function ExternalUser() {
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
    const [tenants, setTenants] = useState([]);
    const [selTenantId, setSelTenantId] = useState(null);

    useEffect(() => {
        const call_reload = ()=> {
            try {
                setWorking(true);
                reload();
            } finally {
                setWorking(false);
            }
        }
        call_reload();
    }, []);
    //
    const reload = async () => {
        try {
            let response = await api.get('/api/manager/tenants-for-ext-users');
            setTenants(response.data);

            response = await api.get('/api/manager/ext-users');
            setUsers(response.data);
        } catch (error) {
            console.error("Error fetching data:", error);
        }
    };

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
                password: password1,
                tenant_id: selTenantId,
            })
            dispatch(setInfoMessage("User added successfully"));
            setEmail('');
            setName('');
            setPassword1('');
            setPassword2('');
            await reload();
        } catch(error) { /*error handled in apiService*/
            console.log(error);
        } finally {
            setWorking( false);
            setPassword1('');
            setPassword2('');
        }
    }

    const handleInactivateUser= async (email) => {
        if (!window.confirm( `Inactive user ${email}?`))
            return
        try {
            setWorking(true);
            const response = await api.delete("/api/manager/ext-users", {
                params: { email }
            })
            dispatch(setInfoMessage("User inactivated successfully"));
            await reload();
        } catch(error) { /*error handled in apiService*/
            console.log(error);
        } finally {
            setWorking( false);
        }
    }

    return (
        <div className={styles["page-container"]}>
            <Title>Add external user</Title>
            <div className={styles["password-update-form"]}>
                <div className={styles["form-group"]}>
                    <div>Tenant:</div>
                    <div>
                        <select
                            value={selTenantId}
                            onChange={e => setSelTenantId(e.target.value)}
                        >
                            <option disabled selected value="">Please select an option</option>
                            {tenants.map((option, index) => (
                                <option key={index} value={option.tenant_id}>{option.name}</option>
                            ))}
                        </select></div>
                </div>
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
                <button type="submit" className={`${styles["submit-btn"]} button`}
                        disabled={isWorking || !selTenantId || !name || !email || !password1 || (password1!== password2)}
                        onClick={handleAddUser}
                >
                    {isWorking ? 'Working...' : 'Add user'}
                </button>
            </div>
            <div className={styles.projectList}>
                {users.map((user, idx) =>
                    <div key={idx} className={`${styles["projectItem"]} list-item ${user.active?"-active": "-inactive"}`}>
                        <div>{user.tenant_name}</div>
                        <div>{user.name}</div>
                        <div>{user.email}</div>
                        <div>{user.active.toString()}</div>
                        {!user.active? <div></div>: <div className={"fa-icon"} onClick={()=>handleInactivateUser(user.email)} title={"Inactivate user"}>
                            <FaTrashCan/>
                        </div>}
                    </div>)
                }
            </div>
        </div>
    );
}


export default ExternalUser;