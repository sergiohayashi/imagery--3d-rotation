import React, {useContext, useEffect, useState} from "react";
import {
    setCurrentChatId,
    setCurrentProject,
    setProjectList,
    setShowNav, setModel, setModelList, setUseModelAlternatives, setErrorMessage,
    setPreferences, setOpenModelList, setCurrentFileContext, setTemporaryChat
} from "../../redux/actions";
import {AppContext} from "../../redux/AppContext";
import { MdOutlineHourglassEmpty } from "react-icons/md";
import {useNavigate} from "react-router-dom";
import {useMsal} from "@azure/msal-react";
import styles from './TopLayout.module.css'
import ContextModal from "../ContextModal/ContextModal";
import 'rc-slider/assets/index.css';
import {useApi} from "../../hooks/useApi";
import {FaCheck, FaChevronLeft, FaChevronRight, FaImage, FaSearch, FaVideo, FaHourglass} from "react-icons/fa";
import {FaBars, FaBookmark, FaGlobe, FaPlus, FaRegBookmark, FaXmark} from "react-icons/fa6";
import {GoHourglass } from "react-icons/go";
import {GoTriangleDown} from "react-icons/go";
import Logo from "../Logo/Logo";
import {RxExternalLink, RxText} from "react-icons/rx";
import {simpleDateFormatter} from "../../helpers/formatters";
import {LuAudioLines, LuFileStack, LuImage, LuMessageSquareDashed} from "react-icons/lu";
import {PiCaretUpDownFill} from "react-icons/pi";
import {
    keyFor, keyForBookmarkedModels,
} from "../../preferences";
import {BsCodeSquare} from "react-icons/bs";
import FileContextTop from "../FileContextTop/FileContextTop";
import {Title} from "../Headings/Heading";
// Debounce function
let debounceTimer;
const debounce = (func, delay) => {
    return function() {
        const context = this;
        const args = arguments;
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => func.apply(context, args), delay);
    }
}

const toKilo = (d) => {
    if (!d) return d;
    if (typeof(d) == 'number') {
        if (d >= 1000000) {
            return Math.trunc(d / 1000000) + "M";
        } else if (d > 1000) {
            return Math.trunc(d / 1000) + "K"
        } else return Math.trunc(d).toString();
    }
    return d;
}

const toMax3Decimal = (d) => {
    if (typeof(d)!= 'number') return d;
    return Math.round(d*1000)/1000;
}

const MAX_ALTERNATIVES = 7

const reasoningEffortPreferenceKey = (name) => {
    return `reasoning_effort--${name}`;
}

function TopMenu() {
    const {state, dispatch} = useContext(AppContext);
    const {useModel, useModelAlternatives, modelList, preferences, currentFileContext} = state;
    const {projectList, currentProject, showNav, isMobile, profile, openModelList, currentFileContextLength, temporaryChat} = state;
    const {accounts} = useMsal();
    const navigate = useNavigate();
    const [isSearchModalOpen, setSearchModalOpen] = useState(false);
    const [chatSearchText, setChatSearchText] = useState('');
    const [searchChatList, setSearchChatList] = useState([]);
    const [showModelsModal, setShowModelsModal] = useState(null);
    const [showFilesNav, setShowFilesNav] = useState(false);
    const [openModelFilter, setOpenModelFilter] = useState(null);
    const api = useApi();


    useEffect(() => {
        api.get('/api/models')
            .then(response => {
                const models = response.data;
                for (const m of models) {
                    const key = reasoningEffortPreferenceKey(m.name);
                    if (key in preferences) {
                        m.modified_reasoning_effort = preferences[key];
                    }
                }
                dispatch(setModelList(response.data));
                const _default = response.data?.find(item => item.is_default === true) || null;
                if (useModel) {
                    if (!response.data?.some(item => item.name === useModel)) {
                        dispatch(setModel(_default?.name));
                    }
                } else {
                    dispatch(setModel(_default?.name));
                }
            })
            .catch((error) => { /*error handled in apiService*/
            });

        api.get('/api/projects')
            .then(response => {
                dispatch(setProjectList(response.data));
            })
            .catch((error) => { /*error handled in apiService*/
            });

        api.get('/api/open-models')
            .then(response => {
                dispatch(setOpenModelList(response.data));
            })
            .catch((error) => { /*error handled in apiService*/
            });


    }, [accounts]);

    useEffect(() => {
        setSearchChatList([]);
    }, [currentProject]);

    const [isExpensiveModel, setExpensiveModel] = useState(false);

    useEffect(() => {
        if (useModel && modelList) {
            for (let m of modelList) {
                if (m.name === useModel) {
                    setExpensiveModel(m.expensive);
                    break;
                }
            }
        }
    }, [useModel, modelList])

    useEffect(() => {
        if (projectList) {
            if (!currentProject) {
                dispatch(setCurrentProject(projectList[0]));
            } else {
                if (!projectList.map(p => p.id).includes(currentProject.id)) {
                    dispatch(setCurrentProject(projectList[0]));
                }
            }
        } else {
            dispatch(setCurrentProject(null));
        }
    }, [projectList]);

    const handleChatSearch = debounce((text) => {
        api.get("/api/chats/search/fulltext", {
            params: {
                project_id: currentProject.id,
                q: text
            }
        })
            .then(response => {
                setSearchChatList(response.data);
            })
            .catch((error) => { /*error handled in apiService*/
            });
    }, 500); // 500ms delay


    const handleChatHistoryClick = async (chatId) => {
        await dispatch(setCurrentChatId(chatId))
        navigate(`/chat/${chatId}`)
    }

    const modalityFor = (m) => {

        return <>
            {m.indexOf('T')>=0 && <div title={"text"}><RxText size={14}/></div>}
            {m.indexOf('I')>=0 && <div title={"image"}><LuImage size={14}/></div>}
            {m.indexOf('A')>=0 && <div title={"audio"}><LuAudioLines  size={14}/></div>}
            {m.indexOf('V')>=0 && <div title={"video"}><FaVideo   size={14}/></div>}
        </>
        // return <>{d.input_modality} {d.output_modality}</>
    }

    const [showEffortOptions, setShowEffortOptions] = useState(null);
    const effortModal = !!showEffortOptions && (
        <ContextModal
            clickPosition ={showEffortOptions}
            handleClose={() => setShowEffortOptions(null)} closeLabel={"Close"}>
            <div className={styles['modal-container']}>
            {showEffortOptions.options.concat(['(default)']).map((value,index) => (
                <div className={'list-item'}
                    onClick={()=>{
                        const newModelList = modelList.map(m => {
                            if (m.name === showEffortOptions.name) {
                                if (value === '(default)') {
                                    delete m.modified_reasoning_effort
                                } else {
                                    m.modified_reasoning_effort = value;
                                    console.log('modified_reasoning_effort: ', m.modified_reasoning_effort);
                                }
                            }
                            return m;
                        })
                        dispatch(setModelList(newModelList));
                        const key = reasoningEffortPreferenceKey(showEffortOptions.name);
                        if (value === '(default)') {
                            delete preferences[key];
                        } else {
                            preferences[key] = value;
                        }
                        dispatch(setPreferences(preferences));
                        setShowEffortOptions(null);
                    }}
                >{value}</div>
            ))}
            </div>
        </ContextModal>
    )

    const toolSelected = (name, tool) => {
        return keyFor(name, tool) in preferences;
    }

    const toggleToolSelection = (name, tool) => {
        const key = keyFor(name, tool);
        if (key in preferences) {
            delete preferences[key];
            dispatch(setPreferences(preferences));
        } else {
            preferences[key] = true;
            dispatch(setPreferences(preferences));
        }
    }

    const toggleBookmarkedModel = (name) => {
        let bookmarkedModels = preferences[keyForBookmarkedModels] || [];
        if (bookmarkedModels.indexOf(name)>= 0) {
            bookmarkedModels = bookmarkedModels.filter(d=>d !== name);
        } else {
            bookmarkedModels = [...bookmarkedModels, name];
        }
        preferences[keyForBookmarkedModels] = bookmarkedModels;
        dispatch(setPreferences(preferences));
    }


    const isModelBookmarked = (name) => {
        const bookmarkedModels = preferences[keyForBookmarkedModels] || [];
        return bookmarkedModels.indexOf(name)>=0;
    }

    const propModelsDiv = modelList && (
        <div className={styles["data-selection-list"]}>
            <div className={styles['model-list-header']}>
                <div className={`list-item ${styles["data-selection-item-text-lines"]} bold center`}>
                    <div>Main</div>
                    <div className={"relative"}>
                        <div title={"alternative model"}>Alt</div>
                        {(useModelAlternatives || []).length>0 && <>
                            <div className={`fa-icon -small -red ${styles['delete-alternative-all']}`}
                                 onClick={()=>{
                                     dispatch(setUseModelAlternatives([]))
                                 }}
                            >
                                <FaXmark />
                            </div>
                        </>}
                    </div>
                    <div className={styles["center"]}>model</div>
                    <div className={styles["center"]}>reasoning effort</div>
                    {!isMobile && <div className={styles["center"]}>input price</div>}
                    {!isMobile && <div className={styles["center"]}>output price</div>}
                    {!isMobile && <div className={styles["center"]}>context size</div>}
                    {!isMobile && <div className={styles["modality-icons"]}>input</div>}
                    {!isMobile && <div className={styles["modality-icons"]}>output</div>}
                    <div className={styles["option-icons"]}>tools</div>
                    <div className={styles["center"]}><FaRegBookmark/></div>
                    {!isMobile && <div className={styles["center"]}>ref</div>}
                </div>
            </div>
            {(modelList || []).map((d, index) => (
                <div key={index} className={`list-item ${styles["data-selection-item-text-lines"]}`}
                >
                    <div className={styles["data-store-selected"]}>
                        {useModel && d.name === useModel?
                            <div className={"fa-icon -smaller -accept"}>
                                <FaCheck/>
                            </div>:
                            <div className={"fa-icon -smaller  -color-gray"}
                                 onClick={()=> {
                                     if (useModelAlternatives.includes(d.name)) {
                                         dispatch(setUseModelAlternatives(useModelAlternatives.filter(m=>m!==d.name)));
                                     }
                                     dispatch(setModel(d.name));
                                 }}
                            >
                                <FaCheck/>
                            </div>
                        }
                    </div>
                    <div className={styles["data-store-selected"]}>
                        {useModelAlternatives && useModelAlternatives.includes(d.name)?
                            <div className={"fa-icon  -smaller  -accept"}
                                 onClick={()=>{
                                     dispatch(setUseModelAlternatives(useModelAlternatives.filter(m=>m!==d.name)))
                                 }}
                            >
                                <FaPlus/>
                            </div>:
                            <div className={"fa-icon -smaller  -color-gray"}
                                 onClick={()=>{
                                     if (useModelAlternatives.length>=MAX_ALTERNATIVES) {
                                         dispatch(setErrorMessage(`Max number of alternative models is ${MAX_ALTERNATIVES}`));
                                         return;
                                     }
                                     if (d.name === useModel) return;
                                     dispatch(setUseModelAlternatives([...useModelAlternatives, d.name]))
                                 }}
                            >
                                <FaPlus/>
                            </div>
                        }
                    </div>
                    <div className={styles["title-row"]}
                         onClick={() => {
                             dispatch(setModel(d.name));
                             setShowModelsModal(null);
                         }}
                    >
                        <div className={styles["model-icon"]}>
                            <Logo company={d.company}/>
                        </div>
                        <div>
                            <div className={styles["title"]}>{d.name}</div>
                            {d.description && <div className={styles["description"]}>{d.description}</div>}
                        </div>

                        {/*<div className={styles["title"]} title={d.description ?? undefined}>{d.name}</div>*/}
                    </div>
                    <div className={`${styles["effort"]} ${d.effort_options?.length>0 && 'pointer'}`}
                         onClick={d.effort_options?.length>0? (e)=> {
                             const rect = e.target.getBoundingClientRect();
                             setShowEffortOptions({
                                 top:rect.top,
                                 left:rect.left,
                                 name: d.name,
                                 options: (d.effort_options || [])
                             });
                         }: undefined}
                    >
                        <div>{d.modified_reasoning_effort?
                            (<div className={styles['modified']}>{d.modified_reasoning_effort}</div>):
                            (d.reasoning_effort? d.reasoning_effort: null)}</div>
                        {d.effort_options.length>0 && <div><PiCaretUpDownFill size={14}/></div>}
                    </div>
                    {!isMobile && <div className={`${styles["right"]} ${d.expensive ? styles["expensive"] : ''}`}>{d.input_price}</div>}
                    {!isMobile && <div className={`${styles["right"]} ${d.expensive ? styles["expensive"] : ''}`}>{d.output_price || (d.unit_price?`${d.unit_price}/u`:'')}</div>}
                    {!isMobile && <div className={styles["right"]}>{d.max_token}</div>}
                    {!isMobile && <div className={styles["modality-icons"]}>{modalityFor(d.input_modality)}</div>}
                    {!isMobile && <div className={styles["modality-icons"]}>{modalityFor(d.output_modality)}</div>}
                    <div className={styles["option-icons"]}>
                        {d?.has_search && <div
                            title={"web search supported"}
                            onClick = {()=> {
                                toggleToolSelection(d.name, 'use_search')
                            }}
                            className={`${toolSelected(d.name,'use_search')?styles['modified']:''} pointer-with-underline`}
                        ><FaGlobe size={14}/></div>}
                        {d?.has_code && <div
                            title={"code interpreter supported"}
                            onClick = {()=> {
                                toggleToolSelection(d.name, 'use_code')
                            }}
                            className={`${toolSelected(d.name,'use_code')?styles['modified']:''} pointer-with-underline`}
                        ><BsCodeSquare   size={14}/></div>}
                        {d?.has_image_generation && <div
                            title={"image generation supported (by enabling image generation tool) "}
                            onClick = {()=> {
                                toggleToolSelection(d.name, 'use_image_generation')
                            }}
                            className={`${toolSelected(d.name,'use_image_generation')?styles['modified']:''} pointer-with-underline`}
                        ><FaImage size={14}/></div>}
                        {/*{d?.has_url_context && <div*/}
                        {/*    title={"URL context supported"}*/}
                        {/*><IoLinkSharp size={14}></IoLinkSharp></div>}*/}
                    </div>
                    <div className={styles["center"]}
                         onClick = {()=> toggleBookmarkedModel(d.name)}
                    >
                        <div className={"fa-icon -smaller  -color-gray"}>
                            {isModelBookmarked(d.name)?<FaBookmark className={"-main-color"}/>:<FaRegBookmark/>}
                        </div>
                    </div>
                    {!isMobile && <div className={styles["center"]}>
                        {d.link ? <a target={"_blank"} href={d.link}>
                            <div className={"fa-icon"}>
                                <RxExternalLink/>
                            </div>
                        </a> : null}
                    </div>}
                </div>
            ))}
        </div>
    )


    const filteredOpenModelList = !openModelFilter?openModelList:(openModelList || []).filter((d)=> (
        d.name.toLowerCase().includes(openModelFilter.toLowerCase()) ||
        d.company.toLowerCase().includes(openModelFilter.toLowerCase())
    ));

    const openModelsDiv = (<>
        <div className={styles['filter-bar']}>
            <div>Filter:</div>
            <input
                type="text"
                className={'input'}
                value={openModelFilter}
                onChange = {(e) =>setOpenModelFilter(e.target.value)}
            />
        </div>
        <div className={styles["data-selection-list"]}>
            <div className={styles['model-list-header']}>
                <div className={`list-item ${styles["data-selection-item-text-lines--open"]} bold center`}>
                    <div>Main</div>
                    <div className={"relative"}>
                        <div title={"alternative model"}>Alt</div>
                        {(useModelAlternatives || []).length>0 && <>
                            <div className={`fa-icon -small -red ${styles['delete-alternative-all']}`}
                                 onClick={()=>{
                                     dispatch(setUseModelAlternatives([]))
                                 }}
                            >
                                <FaXmark />
                            </div>
                        </>}
                    </div>
                    <div className={styles["center"]}>company</div>
                    <div className={styles["center"]}>model</div>
                    <div className={styles["center"]}>best provider</div>
                    {!isMobile && <div className={styles["center"]}>input price</div>}
                    {!isMobile && <div className={styles["center"]}>output price</div>}
                    {!isMobile && <div className={styles["center"]}>context size</div>}
                    <div className={styles["center"]}><FaRegBookmark/></div>
                    {!isMobile && <div className={styles["center"]}>ref</div>}
                </div>
            </div>
            {(filteredOpenModelList || []).map((d, index) => (
                <div key={index} className={`list-item ${styles["data-selection-item-text-lines--open"]}`}
                >
                    <div className={styles["data-store-selected"]}>
                        {useModel && d.name === useModel?
                            <div className={"fa-icon -smaller -accept"}>
                                <FaCheck/>
                            </div>:
                            <div className={"fa-icon -smaller  -color-gray"}
                                 onClick={()=> {
                                     if (useModelAlternatives.includes(d.name)) {
                                         dispatch(setUseModelAlternatives(useModelAlternatives.filter(m=>m!==d.name)));
                                     }
                                     dispatch(setModel(d.name));
                                 }}
                            >
                                <FaCheck/>
                            </div>
                        }
                    </div>
                    <div className={styles["data-store-selected"]}>
                        {useModelAlternatives && useModelAlternatives.includes(d.name)?
                            <div className={"fa-icon  -smaller  -accept"}
                                 onClick={()=>{
                                     dispatch(setUseModelAlternatives(useModelAlternatives.filter(m=>m!==d.name)))
                                 }}
                            >
                                <FaPlus/>
                            </div>:
                            <div className={"fa-icon -smaller  -color-gray"}
                                 onClick={()=>{
                                     if (useModelAlternatives.length>=MAX_ALTERNATIVES) {
                                         dispatch(setErrorMessage(`Max number of alternative models is ${MAX_ALTERNATIVES}`));
                                         return;
                                     }
                                     if (d.name === useModel) return;
                                     dispatch(setUseModelAlternatives([...useModelAlternatives, d.name]))
                                 }}
                            >
                                <FaPlus/>
                            </div>
                        }
                    </div>
                    <div>
                        <div title={d.description ?? undefined}>{d.company}</div>
                    </div>
                    <div className={styles["title-row"]}
                         onClick={() => {
                             dispatch(setModel(d.name));
                             setShowModelsModal(null);
                         }}
                    >
                        <div className={styles["title"]}>{d.name}</div>
                        {d.description && <div className={styles["description"]}>{d.description}</div>}
                    </div>
                    <div className={`${styles["right"]} ${d.expensive ? styles["expensive"] : ''}`}>{d.best_provider?.provider}</div>
                    {!isMobile && <div className={`${styles["right"]} ${d.expensive ? styles["expensive"] : ''}`}>{toMax3Decimal(d.best_provider?.pricing?.output)}</div>}
                    {!isMobile && <div className={`${styles["right"]} ${d.expensive ? styles["expensive"] : ''}`}>{toMax3Decimal(d.best_provider?.pricing?.output)}</div>}
                    {!isMobile && <div className={`${styles["right"]}`}>{toKilo(d.best_provider?.context_length)}</div>}
                    <div className={"center-flex"}
                         onClick = {()=> toggleBookmarkedModel(d.name)}
                    >
                        <div className={"fa-icon -smaller  -color-gray"}>
                            {isModelBookmarked(d.name)?<FaBookmark className={"-main-color"}/>:<FaRegBookmark/>}
                        </div>
                    </div>
                    {!isMobile && <div className={styles["center"]}>
                        <a target={"_blank"} href={`https://huggingface.co/${d.id}`}>
                            <div className={"fa-icon"}>
                                <RxExternalLink/>
                            </div>
                        </a>
                    </div>}
                </div>
            ))}
        </div>
        </>
    )

    const [modelGroup, setModelGroup] = useState('frontier');

    const modelsModal = !!showModelsModal && (
        <ContextModal
            clickPosition={showModelsModal}
            handleClose={(e) => setShowModelsModal(null)}>
            <div className={styles["data-selection-top"]}>
                <div className={styles['model-list-header']}>
                    <div className={"pre"}>
                        <div>selected model: <span className={"bold"}>{useModel}</span></div>
                        <div className={"wrap"}>alternative models: <span className={"bold"}>{useModelAlternatives.join(' | ')}</span></div>
                    </div>
                    <div className={`list-item ${styles["data-selection-item-text-lines"]} bold center`}></div>
                </div>
                <div className={styles['tab-panel']}>
                    <div
                        className={styles['tab-btn']}
                    >&nbsp;</div>
                    <div
                        className={modelGroup!=='open'?styles['tab-btn--active']:styles['tab-btn']}
                        onClick={()=>setModelGroup('frontier')}
                    >Frontier Models</div>

                    {(openModelList || []).length>0 ? <div
                        className={modelGroup==='open'?styles['tab-btn--active']:styles['tab-btn']}
                        onClick={()=>setModelGroup('open')}
                    >Open Models (via HuggingFace)</div>:<div
                        className={styles['tab-btn--disabled']}
                    >Open Models (via HuggingFace)</div>}
                    <div
                        className={styles['tab-btn']}
                    >&nbsp;</div>
                </div>
                <div className={modelGroup!=='open'?'display-block':'display-none'}>{propModelsDiv}</div>
                <div className={modelGroup==='open'?'display-block':'display-none'}>{openModelsDiv}</div>
            </div>
        </ContextModal>
    )

    const chatSearchModal = !!isSearchModalOpen && (
        <ContextModal
            clickPosition={isSearchModalOpen}
            nonblocking={true}
            handleClose={() => setSearchModalOpen(null)}
            closeLabel={"Close"}>
            <div className={styles["search-modal-list-container"]}>
                <div className={styles["model-list-search-container"]}>
                    Search: <input type={"text"}
                                   value={chatSearchText ?? ''}
                                   className={`${styles["modal-list-search-input"]} input`}
                                   autoFocus
                                   onChange={e => {
                                       setChatSearchText(e.target.value);
                                       handleChatSearch(e.target.value);
                                   }}/>
                </div>
                <div className={styles["model-list-search-result-container"]}>
                    <div className={styles["model-list-search-result-inner-scroll"]}>
                        {searchChatList.map((chat, index) => (
                            <div className={"selection-list-item"} key={index} onClick=
                                {() => {
                                    handleChatHistoryClick(chat.id);
                                    if (isMobile)
                                        setSearchModalOpen(null);
                                }}>
                                <div className={styles['modal-list-title']}>{chat.title}</div>
                                <div className={styles['modal-list-date']}>{simpleDateFormatter(chat.startTime)}</div>
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </ContextModal>
    )

    const newChatHandler = async (e) => {
        // Ctrl on Windows/Linux, ⌘ on macOS, or middle-click
        const openInNewTab = e.ctrlKey || e.metaKey || e.button === 1;
        if (openInNewTab) {
            window.open("/#/chat", '_blank', 'noopener,noreferrer');
        } else {
            const r = await api.get(`/api/chats/get-new`,);
            const _chatId = r.data?.chat_id;
            await dispatch(setCurrentChatId(_chatId))
            navigate(`/chat/${_chatId}`)
        }
    }

    const switchShowFilesNav = async ()=> {
        dispatch(setShowFilesNav(!showFilesNav));
    }

    const fileContextModal = (
        <div className={`${styles["files-nav-window"]} ${showFilesNav? "display-block":"display-none"}`}>
            <div className={styles["file-context-header"]}>
                {/*<Title>work with Files</Title>*/}
                <div className={"fa-icon -larger-x"}
                    onClick = {()=>setShowFilesNav(false)}
                 >
                     <FaXmark/>
                 </div>
            </div>
            <FileContextTop/>
        </div>
    )

    const temporaryChatHandler = async (e) => {

        const r = await api.get(`/api/chats/get-new`,);
        const _chatId = r.data?.chat_id;
        await dispatch(setCurrentChatId(_chatId))
        await dispatch(setTemporaryChat(!temporaryChat));
        navigate(`/chat/${_chatId}`)
    }

    // const googleSearchToggle = async()  => {
    //     dispatch(setUseSearch(!useSearch));
    // }
    // const codeInterpreterToggle = async()  => {
    //     dispatch(setUseCode(!useCode));
    // }
    //
    // const agenticModeToggle = async()  => {
    //     dispatch(setAgenticMode(!agenticMode));
    // }

    const left = (
        <div className={styles["header-left"]}>
            <div className={"fa-icon -larger"} onClick={() => dispatch(setShowNav(!showNav))}>
                <FaBars/>
            </div>
            {!isMobile && <div><span className={styles["top-title"]}>{profile?.tenant_name}</span></div>}
        </div>
    )
    return (<>
            <div className={styles["header-left"]}></div>
            <div className={styles["header-right"]}>
            {currentProject && (
                <>
                    {/* <div onClick={temporaryChatHandler}
                         title={"Temporary chat"}
                    >
                        {temporaryChat ? 
                            <div className={"fa-icon -selected-2"}>
                                <LuMessageSquareDashed />
                            </div> : 
                            <div className={"fa-icon"}>
                                <LuMessageSquareDashed />
                            </div>}
                    </div> */}

                    <div className={styles['model-options']}>
                        <div className={styles['use-model-container']}
                             onClick={(e) => {
                                 const rect = e.target.getBoundingClientRect();
                                 setShowModelsModal({top: rect.top, left: rect.left})
                                 setOpenModelFilter(null);
                             }} title="use model">

                            <div className={`pointer-icon-no-width ${styles["use-model"]}`}>
                                <div>
                                    {isExpensiveModel ? <div className={styles['expensive-model']}>{useModel}</div> :
                                        <div className={styles['simple-model']}>{useModel || "default"}</div>}
                                    {useModelAlternatives && useModelAlternatives.length>0 && !temporaryChat &&
                                        <div className={styles['alternatives-model']}>
                                            {useModelAlternatives.map((m,index)=>
                                                <div key={index} className={`icon-on-hover-wrapper ${styles["alternative-names"]}`}
                                                >
                                                    <div>{m}</div>
                                                    <div className={`fa-icon -small -red ${styles["delete-icon"]}`}
                                                        onClick={(e)=> {
                                                            e.stopPropagation();
                                                            dispatch(setUseModelAlternatives(useModelAlternatives.filter(model=>model!==m)));
                                                        }}
                                                    >
                                                        <FaXmark />
                                                    </div>
                                                </div>)}
                                        </div>
                                    }
                                </div>
                                <GoTriangleDown size={20}/>
                            </div>
                        </div>
                    </div>
                    {/* <div className={"fa-icon"} onClick={async (e) => {
                        const rect = e.target.getBoundingClientRect();
                        setSearchChatList([]);
                        setChatSearchText('');
                        setSearchModalOpen({top: rect.top, left: rect.left})
                    }}
                         title={"Search"}
                    >
                        <FaSearch/>
                    </div> */}
                    <div className={"fa-icon"} onClick={newChatHandler}
                         title={"New chat"}
                    >
                        <FaPlus />
                    </div>
                    {/* <div className={styles['file-context-panel']}
                         onClick={(e) => setShowFilesNav(!showFilesNav)}
                    >
                        {currentFileContext?.id ?
                            <div className={styles["file-context-count"]}>
                                <LuFileStack />
                                <div>{`${currentFileContext.title} (${currentFileContextLength})`}</div>
                                <div className={'icon-on-hover-wrapper'}>
                                    <div className={`fa-icon -smaller -red ${styles["delete-icon"]}`}
                                         onClick={(e)=> {
                                             e.stopPropagation();
                                             dispatch(setCurrentFileContext(null));
                                         }}
                                    >
                                        <FaXmark />
                                    </div>
                                </div>
                            </div>:<div className={"fa-icon"}
                                title={"work with files"}
                            >
                                <LuFileStack />
                            </div>
                        }
                    </div> */}
                </>
            )}
        </div>
        {isSearchModalOpen && chatSearchModal}
        {modelsModal}
        {effortModal}
        {fileContextModal}
    </>)
}

export default TopMenu;