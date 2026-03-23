import React, {useRef, useEffect, useImperativeHandle, forwardRef, useContext, useState, memo} from 'react';
import styles from './Chat.module.css';
import MonacoEditor from 'react-monaco-editor';
import { ThemeContext } from "../../redux/ThemeContext";
import {AppContext} from "../../redux/AppContext";

const PromptEditor = forwardRef(({
                                     isCodeEditor,
                                     // version,
                                     /* uncontrolled input */
                                     defaultValue = '',
                                     /* write-through callback that does NOT cause re-renders in the parent */
                                     onValueChange,
                                     /* called once just before unmount, last chance to persist */
                                     onWillUnmount,
                                     // value,
                                     // onChange,
                                     onControlEnter,
                                     onDidPaste,
                                     chatLayout,
                                     showMinMap = false
                                 }, ref) => {
    const { theme } = useContext(ThemeContext);
    const editorRef = useRef(null);
    const containerRef = useRef(null);
    const sizeRef = useRef({ width: 0, height: 0 });
    const { state } = useContext(AppContext);
    const { resizeDetected } = state;
    const [localValue, setLocalValue] = useState(defaultValue);
    const latestValue = useRef(defaultValue);

    useEffect(()=> {
        handleResize();
    }, [resizeDetected])

    useEffect(() => {
        setLocalValue(defaultValue);
        latestValue.current = defaultValue;
    }, [defaultValue]);

    const change = (v) => {
        latestValue.current = v;   // <— synchronous
        setLocalValue(v);          // <— asynchronous
        onValueChange?.(v);        // parent writes it in its own ref
    };

    useEffect(
        () => () => onWillUnmount?.(latestValue.current),
        [],                     // no deps → run only on unmount
    );

    /* 4. imperative API that the parent can call */
    useImperativeHandle(
        ref,
        () => ({
            getValue: () => latestValue.current,
            setValue: (v) => change(v),
        }),
        [localValue],
    );


    const handleResize = () => {
        if (containerRef.current) {
            const currentWidth = containerRef.current.offsetWidth;
            const currentHeight = containerRef.current.offsetHeight;
            if (
                currentWidth !== sizeRef.current.width ||
                currentHeight !== sizeRef.current.height
            ) {
                sizeRef.current = { width: currentWidth, height: currentHeight };
                if (editorRef.current) {
                    // console.log( 'layout() called');
                    editorRef.current.layout();
                }
            } else {
                // console.log( 'size not modified');
            }
        }
    };

    return isCodeEditor ? (
        <div ref={containerRef} style={{ width: '100%', height: '100%' }}>
            <MonacoEditor
                width="100%"
                height="100%"
                maxHeight="100%"
                minHeight="0"
                language="plaintext"
                theme={theme === "dark" ? "vs-dark" : "vs"}
                value={localValue}
                options={{
                    selectOnLineNumbers: true,
                    tabSize: 2,
                    fontSize: 12,
                    wordWrap: 'on',
                    lineNumbers: 'off',
                    folding: false,
                    scrollbar: { horizontal: 'hidden' },
                    glyphMargin: false,
                    contextmenu: false,
                    minimap: { enabled: showMinMap },
                    quickSuggestions: false,
                    codeLens: false,
                }}
                onChange={(newValue, e) => change(newValue)}
                editorDidMount={(editor, monaco) => {
                    editor.addCommand(
                        monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter,
                        async () => {
                            console.log('call OnEnter(monaco)!');
                            onControlEnter?.();
                        }
                    );
                    editorRef.current = editor;
                    // Get the editor's DOM node
                    const editorElement = editor.getDomNode();
                    if (editorElement) {
                        editorElement.addEventListener("paste", onDidPaste);
                    }

                    // Cleanup event listener when component unmounts
                    return () => {
                        if (editorElement) {
                            editorElement.removeEventListener("paste", onDidPaste);
                        }
                    };
                }}
            />
         </div>
    ) : (
        <textarea
            style={{width: "100%", border: "none", padding: "8px" }}
            className={`code ${styles['prompt-textarea-mobile']}`}
            value={localValue}
            onPaste ={onDidPaste}
            onChange={(e) => change(e.target.value)}
            onKeyDown={(event) => {
                if (event.ctrlKey && event.key === 'Enter') {
                    if (onControlEnter) {
                        event.preventDefault();
                        onControlEnter();
                    }
                }
            }}
        />
    );
});

export default memo(PromptEditor);
