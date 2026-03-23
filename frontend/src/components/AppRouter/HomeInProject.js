import {useContext, useEffect, useRef} from "react";
import {AppContext} from "../../redux/AppContext";
import {setCurrentChatId} from "../../redux/actions";
import {useNavigate} from "react-router-dom";
import {useApi} from "../../hooks/useApi";

const HomeInProject = () => {
    const { state, dispatch } = useContext(AppContext);
    const navigate = useNavigate();
    const calledRef = useRef(false); // <<< for preventing multiple calls

    const api = useApi();

    const gotoNewChat = async () => {
        if (calledRef.current) return; // Prevent multiple triggers
        calledRef.current = true;

        const r = await api.get(`/api/chats/get-new`,);
        const _chatId = r.data?.chat_id;
        await dispatch(setCurrentChatId(_chatId))
        navigate(`/chat/${_chatId}`)
    }

    useEffect(() => {
        gotoNewChat();
        // Do NOT put gotoNewChat in dep array, this is intentional!
        // eslint-disable-next-line
    }, []); // Only run once on mount

    return <div>HomeInProject.js here!</div>

}

export default HomeInProject;