import axios from 'axios';

export const uploadDocumentsUsingS3 = async (api, file, projectId, chatId) => {
    try {
        const contentType = file.type || "application/octet-stream";
        // Step 1: Get pre-signed URL from your FastAPI backend
        const presignedResp = await api.post(`/api/upload/generate-upload-url`,
            {
                filename: file.name,
                content_type: contentType
            }
        );
        const presignedUrl = presignedResp.data.presigned_url;
        const s3Key = presignedResp.data.s3_key;
        const assignedFileName = presignedResp.data.filename;

        // Step 2: Use pre-signed URL to directly upload file to S3
        await axios.put(presignedUrl, file, {
            headers: {
                "Content-Type": contentType,
            },
        });

        // Step 3: Notify your backend about the upload completion (optional but recommended)
        const response = await api.post(`/api/upload/confirm-upload`,
            {
                filename: file.name || assignedFileName,
                s3_key: s3Key,
                project_id: projectId,
                chat_id: chatId,
                content_type: contentType
            });

        return {
            file_url: response.data?.file_url,
            content_type: contentType
        };

    } catch (error) {
        console.error('Error uploading the file:', error);
        throw error;
    }
};
