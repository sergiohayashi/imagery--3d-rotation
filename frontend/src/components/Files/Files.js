import React, {useState, useEffect, useContext} from 'react';
import {AppContext} from "../../redux/AppContext";
import styles from "./Files.module.css"
import { useNavigate  } from 'react-router-dom';
import {useApi} from "../../hooks/useApi";
import {FaAngleLeft, FaEdit} from "react-icons/fa";
import {Title} from "../Headings/Heading";
import {FileCard} from "./FileCard";
import {GrCaretNext, GrCaretPrevious, GrChapterPrevious} from "react-icons/gr";

const pageSize = 20

function Files() {
    const { state, dispatch } = useContext(AppContext);
    const { currentProject } = state;
    const navigate = useNavigate();
    const api = useApi();
    const [files, setFiles] = useState([]);
    const [selection, setSelection] = useState({
        category: 'g',
        start: 0
    })

    useEffect(() => {
        fetchFiles();
    }, [currentProject, selection]);

    const fetchFiles = async () => {
        try {
            const response = await api.get('/api/files', {
                params: {
                    project_id: currentProject.id,
                    start: selection.start,
                    size: pageSize,
                    category: selection.category
                }
            });
            setFiles(response.data);
        } catch (error) {
            // handled by api
        }
    };

    const pageNext = ()=> {
        if (files.length>= pageSize) {
            setSelection({...selection, start: selection.start+pageSize});
        }
    }

    const pagePrev = (_start=undefined)=> {
        if (_start === undefined) {
            _start = selection.start-pageSize;
        }

        if (selection.start> 0) {
            setSelection({...selection, start: Math.max(0, _start)});
        }
    }

    const switchCategory = (c) => {
        if (c === selection.category) return;
        setSelection({
            category: c,
            start: 0
        })
    }

    const filesList =  files && (
        <div className={styles['file-flow']}>
            {files.map((f, idx) => (
                <FileCard message={f} onRefresh={fetchFiles}/>
            ))}
        </div>
    )

    return (
        <div className={styles.container}>
            {/*<div className={"title-with-back"}>*/}
            {/*    <a onClick={() => navigate(-1)} className={"fa-icon"}>*/}
            {/*        <FaAngleLeft/>*/}
            {/*    </a>*/}
            {/*    <Title>Files</Title>*/}
            {/*</div>*/}

            <div className={styles['tab-panel']}>
                <div
                    className={styles['tab-btn']}
                >&nbsp;</div>
                <div
                    className={selection.category==='g'?styles['tab-btn--active']:styles['tab-btn']}
                    onClick={()=>switchCategory('g')}
                >Generated</div>
                <div
                    className={selection.category==='u'?styles['tab-btn--active']:styles['tab-btn']}
                    onClick={()=>switchCategory('u')}
                >Uploaded</div>
                <div
                    className={styles['tab-btn']}
                >&nbsp;</div>
            </div>
            <div className={styles.contextList}>
                {filesList}
            </div>
            <hr className={"separator"}/>
            <div className={styles['page-panel']}>
                {selection.start> 0 && <>
                    <div className={"fa-icon"}
                         onClick={()=> pagePrev(0)}
                    >
                        <GrChapterPrevious />
                    </div>
                <div className={"fa-icon"}
                    onClick={()=> pagePrev()}
                >
                    <GrCaretPrevious/>
                </div>
                </>}
                {files.length>= pageSize && <div className={"fa-icon"}
                    onClick={()=>pageNext()}
                >
                    <GrCaretNext/>
                </div>}
            </div>
            {/*{isDialogOpen && modal}*/}
        </div>
    );
}

export default Files;
