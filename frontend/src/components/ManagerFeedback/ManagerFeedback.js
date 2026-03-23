// import styles from "./ManagerFeedback.module.css"
// import React, {useContext, useEffect, useState} from "react";
// import {useNavigate} from "react-router-dom";
// import {ThemeContext} from "../../redux/ThemeContext";
// import {AppContext} from "../../redux/AppContext";
// import {useMsal} from "@azure/msal-react";
// // import { getApi } from '../../services/apiService';
// import ContextModal from "../ContextModal/ContextModal";
// import {formatDateMonthDay} from "../../helpers/formatters";
// import {useApi} from "../../hooks/useApi";
// import {FaPlusCircle} from "react-icons/fa";
// import {FaPlus} from "react-icons/fa6";
// import {Title} from "../Headings/Heading";
//
// function ManagerFeedback() {
//     const { theme } = useContext(ThemeContext);
//     const navigate = useNavigate();
//     const [feedbackList, setFeedbackList] = useState([]);
//     const { state, dispatch } = useContext(AppContext);
//     const { instance } = useMsal();
//     const api = useApi();
//
//     useEffect(() => {
//         fetchFeedback();
//     }, []);
//
//     const fetchFeedback = async () => {
//         try {
//             const response = await api.get('/api/manager/feedback');
//             setFeedbackList(response.data);
//         } catch (error) {
//             console.error("Error fetching feedback:", error);
//         }
//     };
//
//     // const formatDate = (date) => {
//     //     if (!date) return null;
//     //     const year = date.getFullYear();
//     //     const month = String(date.getMonth() + 1).padStart(2, '0'); // Months are zero-based
//     //     const day = String(date.getDate()).padStart(2, '0');
//     //
//     //     return `${month}-${day}`;
//     // };
//     //
//     const [isCommentModalOpen, setCommentModalOpen]=  useState(false);
//     const [commentFeedbackId, setCommentFeedbackId] = useState(null);
//     const [commentText, setCommentText] = useState('');
//
//     const commentModal = !!isCommentModalOpen && (
//         <ContextModal
//             show={isCommentModalOpen}
//             clickPosition = {isCommentModalOpen}
//             handleClose={() => {
//                 setCommentModalOpen( false);
//             }}
//         >
//             <div className={`${styles["modal-container"]} context-modal-margin`}>
//                 <textarea
//                     type={"text"}
//                     className={styles["comment-textarea"]}
//                     autoFocus
//                     value={commentText}
//                     onChange = {e=>setCommentText(e.target.value)}/>
//                 <button
//                     className={"button"}
//                     onClick = {async () => {
//                         await handleAddComment(commentFeedbackId, commentText);
//                         setCommentModalOpen(null);
//                     }}
//                 >Post</button>
//             </div>
//         </ContextModal>
//     )
//
//
//     const handleAddComment= async (id, comment) => {
//         await api.post(`/api/manager/feedback/${id}/comment`, {
//             text: comment
//         });
//         await fetchFeedback()
//     }
//
//
//     return (
//         <>
//             <Title>Feedback</Title>
//             <div className={styles['container']}>
//             <div className={styles['container-grid']}>
//                 <div className={`${styles['container-grid-row']} ${styles['container-grid-header-row']}`}>
//                     <div className={styles['header']}>Created At</div>
//                     <div className={styles['header']}>User Name</div>
//                     {/*<div className={styles['header']}>User Email</div>*/}
//                     <div className={styles['header']}>Category</div>
//                     <div className={styles['header']}>Text</div>
//                     <div className={styles['header']}>Attachments</div>
//                     <div className={styles['header']}>Comments</div>
//                 </div>
//                 {feedbackList.map((feedback, index) => (
//                     <div className={`${styles['container-grid-row']} list-item`} key={index}>
//                         {feedback.created_at && <div>{formatDateMonthDay(new Date(feedback.created_at))}</div>}
//                         {!feedback.created_at && <div></div>}
//                         <div title={feedback.user_email}>{feedback.user_name}</div>
//                         {/*<div>{feedback.user_email}</div>*/}
//                         <div>{feedback.category}</div>
//                         <div className={"code-view"}>{feedback.text}</div>
//                         <div className={styles['attachments']}>
//                             {feedback.attachment_files && feedback.attachment_files.map((file, fileIndex) => (
//                                 <a key={fileIndex} href={file} target="_blank" rel="noopener noreferrer">
//                                     <img src={file} alt={`Attachment ${fileIndex + 1}`}
//                                          className={styles['thumbnail']}/>
//                                 </a>
//                             ))}
//                         </div>
//                         <div className={"code-view"}>
//                             <div className="fa-icon"
//                                 onClick={(e) => {
//                                     const rect = e.target.getBoundingClientRect();
//                                     setCommentFeedbackId(feedback.id);
//                                     setCommentText('');
//                                     setCommentModalOpen({top: rect.top, left: rect.left})
//                                 }}>
//                                     <FaPlus/>
//                                     {/*<img*/}
//                                     {/*    src={theme == "dark" ? "/icons8-add-50-dark.png" : "/icons8-add-50-light.png"}*/}
//                                     {/*    alt="Add a new comment"/>*/}
//                                 {/*</a>*/}
//                             </div>
//                             {feedback.comments.map((comment, c_idx) => (
//                                 <div className={styles["comment-entry"]}>
//                                     <div>{comment.text}</div>
//                                     {comment.created_by && <div className={styles["comment-meta"]}>by {comment.created_by} at {formatDateMonthDay(comment.created_at)}</div>}
//                                 </div>
//                             ))}
//                         </div>
//                     </div>
//                 ))}
//             </div>
//             </div>
//             {commentModal}
//         </>
//     );
// }
//
//
// export default ManagerFeedback;
