// // src/components/ContextArtifact/SystemMessage.js
// import React, {useState, useEffect, useContext, useRef} from 'react';
// import MaxModal from '../MaxModal/MaxModal'
// // import { getApi } from '../../services/apiService';
// import {AppContext} from "../../redux/AppContext";
// import styles from "./Feedback.module.css"
// import { useMsal } from "@azure/msal-react";
// import {ThemeContext} from "../../redux/ThemeContext";
// import { useNavigate  } from 'react-router-dom';
// import {setChatLayout, setCurrentUsage, setDisableFromat, setInfoMessage} from "../../redux/actions";
// import SystemMessageEditor from "../SystemMessageEditor/SystemMessageEditor";
// import AssistantWrapper from "../AssistantWrapper/AssistantWrapper";
// import {formatDateMonthDay} from "../../helpers/formatters";
// import {useApi} from "../../hooks/useApi";
// import {FaAngleLeft, FaClipboard} from "react-icons/fa";
// import {FaPaperclip, FaPlus, FaTrashCan} from "react-icons/fa6";
// import {Title} from "../Headings/Heading";
//
//
// function Feedback() {
//     const [feedbacks, setFeedbacks] = useState([]);
//     const [selectedMessage, setSelectedMessage] = useState(null);
//     const [dialogText, setDialogText] = useState('');
//     const [dialogTitle, setDialogTitle] = useState('');
//     const [isDialogOpen, setIsDialogOpen] = useState(false);
//     const { state, dispatch } = useContext(AppContext);
//     const { currentProject } = state;
//     const { instance } = useMsal();
//     const { theme } = useContext(ThemeContext);
//     const navigate = useNavigate();
//     const [isSystemMessageDialogShared, setSystemMessageDialogShared] = useState(false)
//     const fileInputRef = useRef(null);
//     const api = useApi();
//
//     useEffect(() => {
//         fetchFeedbacks();
//     }, []);
//
//
//     const fetchFeedbacks = async () => {
//         try {
//             const response = await api.get('/api/feedback');
//             setFeedbacks(response.data);
//         } catch (error) {
//             console.error('Error fetching feedback', error);
//         }
//     };
//
//     const [showSuggestionModal, setShowSuggestionModal] = useState(false);
//     const [loading, setLoading] = useState(false);
//
//     const triggerFileInput = () => {
//         // Trigger the file input click event
//         fileInputRef.current.click();
//     };
//
//     const handleFileChange = async (event) => {
//         const file = event.target.files[0];
//         if (!file) return;
//
//         await handleDropFiles(event.target.files);
//     };
//
//     const handleDropFiles = async (dropFiles) => {
//         if (dropFiles.length<= 0) return;
//         try {
//             setLoading(true);
//             for (let i = 0; i < dropFiles.length; i++) {
//                 // console.log(dropFiles[i]);
//                 await handleFileInput(dropFiles[i]);
//             }
//         } catch (error) {
//             console.error('Error uploading file:', error);
//         } finally {
//             setLoading(false);
//         }
//     };
//
//     const handleFileInput = async (file) => {
//         console.log( file);
//         const formData = new FormData();
//         formData.append('file', file);
//         const response = await api.post('/api/upload', formData, {
//             headers: {
//                 'Content-Type': 'multipart/form-data',
//             },
//         });
//         setAttachmentFileUrl((current) => [...current, {
//             url: response.data.file_url,
//             name: file.name,
//             is_image: file.type.startsWith( 'image')
//         }])
//     }
//
//     const handleSubmitSuggestion = async() => {
//         try {
//             setLoading(true);
//             const response = await api.post('/api/feedback', {
//                 ...suggestionParams,
//                 attachment_files: attachmentFileUrl.map((d)=> d.url)
//             });
//             dispatch( setInfoMessage('Thank you. Your feedback has been received!'));
//             setShowSuggestionModal(false);
//             setAttachmentFileUrl([]);
//             setSuggestionParams({});
//             await fetchFeedbacks()
//         } finally {{
//             setLoading(false);
//         }}
//     }
//
//
//     const [attachmentFileUrl, setAttachmentFileUrl] = useState([]);
//     const [suggestionParams, setSuggestionParams] = useState({})
//
//     const suggestionModal = showSuggestionModal && (
//         <MaxModal
//             show={true}
//             handleClose={()=> setShowSuggestionModal(false)}>
//
//             <div className={styles["suggestion-modal-container"]}>
//                 <Title>Share your feedback</Title>
//                 <div className={styles["suggestion-modal-row"]}>
//                     <div className={styles["suggestion-modal-title"]}>Category</div>
//                     <div className={`${styles["suggestion-modal-input"]} h-w-100`}
//                     ><select
//                         value={suggestionParams.category}
//                         onChange={(e) => {
//                             setSuggestionParams(prev => ({...prev, category: e.target.value}))
//                         }}
//                     >
//                         <option value="">Select category</option>
//                         <option value={"bug"}>bug</option>
//                         <option value={"suggestion"}>suggestion</option>
//                         <option value={"question"}>question</option>
//                         <option value={"other"}>other</option>
//                     </select></div>
//                 </div>
//                 <div className={`${styles["suggestion-modal-row"]} ${styles["suggestion-modal-row-main"]}`}>
//                     <div className={styles["suggestion-modal-title"]}>Your feedback</div>
//                     <div className={`${styles["suggestion-modal-input"]}`}>
//                         <AssistantWrapper
//                             notifyImprovedText={(value) => setSuggestionParams(prev=>({...prev, text: value}))}
//                             message = {suggestionParams.text}
//                         />
//                         <textarea className={"code"}
//                                   value = {suggestionParams.text}
//                                   onChange = {e=> setSuggestionParams(prev=>({...prev, text: e.target.value}))}
//                         ></textarea>
//                     </div>
//                 </div>
//                 <div className={styles["suggestion-modal-row"]}>
//                     <div className={styles["suggestion-modal-title"]}>
//                         <div>Attachment</div>
//                         <div className={"fa-icon"}
//                              onClick={triggerFileInput}
//                         >
//                             <FaPaperclip/>
//                             {/*<img*/}
//                             {/*    src={theme == "dark" ? "/icons8-attach-50-dark.png" : "/icons8-attach-50-light.png"}*/}
//                             {/*/>*/}
//                         </div>
//
//                     </div>
//                     <div className={`${styles["suggestion-modal-input"]} ${styles["suggestion-modal-attachment"]}`}>
//                         {attachmentFileUrl.map((file, idx) => (
//                             <div className={styles["attachment-container"]}>
//                                 {file.is_image && <img className={styles["image-in-thread"]}
//                                                        src={file.url}/>}
//                                 {!file.is_image && <div>{file.name}</div>}
//                                 <div onClick={() => setAttachmentFileUrl((current)=>
//                                     current.filter((_, index)=> index!==idx)
//                                 )}
//                                      className="fa-icon delete" title={"delete entry"}>
//                                     <FaTrashCan/>
//                                     {/*<img*/}
//                                     {/*    src={theme == "dark" ? "/icons8-delete-30-dark.png" : "/icons8-delete-30-light.png"}/>*/}
//                                 </div>
//                             </div>
//                         ))}
//                     </div>
//                 </div>
//                 <hr/>
//                 <div className={styles["suggestion-modal-panel"]}>
//                     <button type={"submit"} className={"button"}
//                             onClick={() => handleSubmitSuggestion()}
//                             disabled={!(suggestionParams.category && suggestionParams.text)}
//                     >
//                         Send
//                     </button>
//                 </div>
//                 <input
//                     type="file"
//                     // accept="application/pdf,text/plain"
//                     style={{display: 'none'}}
//                     ref={fileInputRef}
//                     onChange={handleFileChange}
//                 />
//             </div>
//         </MaxModal>
//     )
//
//
//     const handleDelete = async (id) => {
//         try {
//             await api.delete(`/api/feedbacks/${id}`);
//             // setIsDialogOpen(false);
//             await fetchFeedbacks()
//         } catch (error) {
//             console.error('Error deleting feedback', error);
//         }
//     };
//
//     const handleAddNew = async () => {
//
//     }
//
//     return (
//         <div className={styles.container}>
//             <div className={"title-with-back"}>
//                 <div className={"fa-icon"}
//                      onClick={() => navigate(-1)}>
//                     <FaAngleLeft/>
//                 </div>
//                 <Title>Your feedbacks</Title>
//                 {/*<img src={theme == "dark" ? "/icons8-previous-dark-50.png" : "/icons8-previous-light-50.png"}*/}
//                 {/*     alt="back"/>*/}
//             </div>
//             <div className="fa-icon"
//                  onClick={() => {
//                      setShowSuggestionModal(true);
//                  }}>
//                 <FaPlus/>
//
//                 {/*<img src={theme == "dark" ? "/icons8-add-50-dark.png" : "/icons8-add-50-light.png"}*/}
//                 {/*     alt="new feedback"/>*/}
//                 {/*</a>*/}
//             </div>
//             <div className={styles.contextList}>
//                 <div className={`${styles['content-grid-row']} ${styles['content-grid-header-row']}`}>
//                     <div className={styles['header']}>Created At</div>
//                     <div className={styles['header']}>Feedback</div>
//                     {/*<div className={styles['header']}>User Email</div>*/}
//                     <div className={styles['header']}>Attachments</div>
//                     <div className={styles['header']}>Comments</div>
//                 </div>
//                 {feedbacks.map((feedback, index) => (
//                     <div key={index} className={`${styles["content-grid-row"]} list-item`}>
//                         <div>{formatDateMonthDay(feedback.create_at)}</div>
//                         <div className={styles['feedback']}>{feedback.text}</div>
//                         <div className={styles['attachments']}>
//                             {feedback.attachment_files && feedback.attachment_files.map((file, fileIndex) => (
//                                 <a key={fileIndex} href={file} target="_blank" rel="noopener noreferrer">
//                                     <img src={file} alt={`Attachment ${fileIndex + 1}`}
//                                          className={styles['thumbnail']}/>
//                                 </a>
//                             ))}
//                         </div>
//                         <div className={styles['comments']}>{feedback.comments.map((comment, idx) => (
//                             <div className={styles["comment-entry"]}>
//                                 <div>{comment.text}</div>
//                                 {comment.created_by && <div
//                                     className={styles["comment-meta"]}>by {comment.created_by} at {formatDateMonthDay(comment.created_at)}</div>}
//                             </div>
//                         ))}
//                         </div>
//                     </div>
//                 ))}
//             </div>
//             {/*{isDialogOpen && modal}*/}
//             {suggestionModal}
//         </div>
//     );
// }
//
// export default Feedback;
