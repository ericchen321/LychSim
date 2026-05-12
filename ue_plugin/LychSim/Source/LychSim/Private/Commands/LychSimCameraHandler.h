#pragma once

#include "CameraHandler.h"
#include "CommandHandler.h"

#include "RHI.h"
#include "RHIGPUReadback.h"
#include "RenderResource.h"
#include "Engine/TextureRenderTarget2D.h"

class UFusionCamSensor;
class ULitCamSensor;

struct FLitReadbackRequest
{
    TWeakObjectPtr<ULitCamSensor> Sensor;
    int32 Width = 0;
    int32 Height = 0;

    TUniquePtr<FRHIGPUTextureReadback> Readback;

    bool bEnqueued = false;
};

class FLychSimCameraHandler : public FCommandHandler
{
public:
    void RegisterCommands();

private:
    UFusionCamSensor* GetCamera(const TArray<FString>& Args, FExecStatus& Status);
    TArray<UFusionCamSensor*> GetCameraBatch(const TArray<FString>& Args, FExecStatus& Status);

    FExecStatus GetCameraLocation(const TArray<FString>& Args);
    FExecStatus GetCameraRotation(const TArray<FString>& Args);
    FExecStatus SetCameraLocation(const TArray<FString>& Args);
    FExecStatus SetCameraRotation(const TArray<FString>& Args);
    FExecStatus GetCameraFOV(const TArray<FString>& Args);
    FExecStatus SetCameraFOV(const TArray<FString>& Args);
    FExecStatus IsPoseInvalid(const TArray<FString>& Args);
    FExecStatus GetCameraC2W(const TArray<FString>& Args);

    FExecStatus SetFilmSize(const TArray<FString>& Args);

    FExecStatus GetCameraLit(const TArray<FString>& Pos, const TMap<FString,FString>& Kw, const TSet<FString>& Flags);
    FExecStatus GetCameraLitBatch(const TArray<FString>& Pos, const TMap<FString,FString>& Kw, const TSet<FString>& Flags);
    FExecStatus WarmupCamera(const TArray<FString>& Args);
    FExecStatus GetCameraSeg(const TArray<FString>& Args);
    FExecStatus GetCameraElementSeg(const TArray<FString>& Args);
    FExecStatus GetCameraNormal(const TArray<FString>& Args);
    FExecStatus AnnotateNewObjects(const TArray<FString>& Args);
    FExecStatus ClearAnnotationComponents(const TArray<FString>& Args);
    FExecStatus GetCameraDepth(const TArray<FString>& Args);
    FExecStatus GetCameraAnnotations(const TArray<FString>& Args);
    FExecStatus GetZBuffer(const TArray<FString>& Pos, const TMap<FString,FString>& Kw, const TSet<FString>& Flags);
    FExecStatus GetPointMap(const TArray<FString>& Pos, const TMap<FString,FString>& Kw, const TSet<FString>& Flags);
};
