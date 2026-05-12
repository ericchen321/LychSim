#include "LychSimCameraHandler.h"
#include "LychSimStructuredResponse.h"
#include "CameraHandler.h"
#include "FusionCamSensor.h"
#include "ImageUtil.h"
#include "SensorBPLib.h"
#include "Serialization.h"
#include "Utils/DataUtil.h"
#include "Utils/StrFormatter.h"
#include "UnrealcvLog.h"
#if WITH_EDITOR
#include "Editor.h"
#include "ScopedTransaction.h"
#endif
#include "VisionBPLib.h"
#include "Utils/UObjectUtils.h"
#include "WorldController.h"

#include "Serialization/JsonWriter.h"
#include "Serialization/JsonSerializer.h"

#include "Sensor/CameraSensor/LitCamSensor.h"
#include "Engine/World.h"
#include "CollisionShape.h"

// Binary-capture handlers return raw bytes on success (PNG/NPY) but must still
// emit the structured JSON envelope on failure so Python has one error parser.
static FExecStatus EnvelopeError(const FString& Msg)
{
	FLychSimStructuredResponse R;
	return R.Error(Msg);
}

void FLychSimCameraHandler::RegisterCommands() {
    CommandDispatcher->BindCommand(
        "lych cam get_loc [uint]",
		FDispatcherDelegate::CreateRaw(this, &FLychSimCameraHandler::GetCameraLocation),
		"Get camera location in world space"
    );

	CommandDispatcher->BindCommand(
        "lych cam set_loc [uint] [float] [float] [float]",
		FDispatcherDelegate::CreateRaw(this, &FLychSimCameraHandler::SetCameraLocation),
		"Set camera location in world space"
    );

    CommandDispatcher->BindCommand(
        "lych cam get_rot [uint]",
		FDispatcherDelegate::CreateRaw(this, &FLychSimCameraHandler::GetCameraRotation),
		"Get camera location in world space"
    );

	CommandDispatcher->BindCommand(
        "lych cam set_rot [uint] [float] [float] [float]",
		FDispatcherDelegate::CreateRaw(this, &FLychSimCameraHandler::SetCameraRotation),
		"Set camera rotation in world space"
    );

    CommandDispatcher->BindCommand(
        "lych cam get_fov [uint]",
		FDispatcherDelegate::CreateRaw(this, &FLychSimCameraHandler::GetCameraFOV),
		"Get camera FOV"
    );

	CommandDispatcher->BindCommand(
		"lych cam get_c2w [uint]",
		FDispatcherDelegate::CreateRaw(this, &FLychSimCameraHandler::GetCameraC2W),
		"Get camera C2W transform"
	);

	CommandDispatcher->BindCommand(
		"lych cam is_pose_invalid [uint] [float] [float] [float]",
		FDispatcherDelegate::CreateRaw(this, &FLychSimCameraHandler::IsPoseInvalid),
		"Check whether the target camera position is invalid by a 5cm overlap sphere"
	);

	CommandDispatcher->BindCommand(
		"lych cam is_pose_invalid [uint] [float] [float] [float] [float]",
		FDispatcherDelegate::CreateRaw(this, &FLychSimCameraHandler::IsPoseInvalid),
		"Check whether the target camera position is invalid by overlap sphere with custom radius(cm)"
	);

	CommandDispatcher->BindCommand(
		"lych cam set_film_size [uint] [uint] [uint]",
		FDispatcherDelegate::CreateRaw(this, &FLychSimCameraHandler::SetFilmSize),
		"Set Camera Film Size"
	);

	CommandDispatcher->BindCommandUE(
		"lych cam get_lit",
		FDispatcherDelegateUE::CreateRaw(this, &FLychSimCameraHandler::GetCameraLit),
		"Get png rendering data from lit sensor"
	);

	CommandDispatcher->BindCommand(
		"lych cam warmup [uint]",
		FDispatcherDelegate::CreateRaw(this, &FLychSimCameraHandler::WarmupCamera),
		"Warm up the camera by capturing lit without saving data"
	);

	CommandDispatcher->BindCommand(
		"lych cam get_seg [uint] [str]",
		FDispatcherDelegate::CreateRaw(this, &FLychSimCameraHandler::GetCameraSeg),
		"Get png segmentation data from annotation sensor"
	);

	CommandDispatcher->BindCommand(
		"lych cam get_ele_seg [uint] [str]",
		FDispatcherDelegate::CreateRaw(this, &FLychSimCameraHandler::GetCameraElementSeg),
		"Get png per-element segmentation data from annotation sensor"
	);

	CommandDispatcher->BindCommand(
		"lych cam annotate_new",
		FDispatcherDelegate::CreateRaw(this, &FLychSimCameraHandler::AnnotateNewObjects),
		"Annotate all new objects; note that objects are automatically annotated when added with \"lych obj add\""
	);

	CommandDispatcher->BindCommand(
		"lych cam clear_annot_comps",
		FDispatcherDelegate::CreateRaw(this, &FLychSimCameraHandler::ClearAnnotationComponents),
		"Clear all annotation components"
	);

	CommandDispatcher->BindCommand(
		"lych cam get_depth [uint] [str]",
		FDispatcherDelegate::CreateRaw(this, &FLychSimCameraHandler::GetCameraDepth),
		"Get depth data from annotation sensor"
	);

	CommandDispatcher->BindCommandUE(
		"lych cam get_zbuffer",
		FDispatcherDelegateUE::CreateRaw(this, &FLychSimCameraHandler::GetZBuffer),
		"Get z-buffer data from annotation sensor"
	);

	CommandDispatcher->BindCommand(
		"lych cam get_normal [uint] [str]",
		FDispatcherDelegate::CreateRaw(this, &FLychSimCameraHandler::GetCameraNormal),
		"Get normal data from annotation sensor"
	);

	CommandDispatcher->BindCommand(
		"lych cam get_annots [uint]",
		FDispatcherDelegate::CreateRaw(this, &FLychSimCameraHandler::GetCameraAnnotations),
		"Get png annotations data from annotation sensor"
	);

	CommandDispatcher->BindCommandUE(
		"lych cam get_pointmap",
		FDispatcherDelegateUE::CreateRaw(this, &FLychSimCameraHandler::GetPointMap),
		"Get point map in camera/world/OpenCV space"
	);
}

UFusionCamSensor* FLychSimCameraHandler::GetCamera(const TArray<FString>& Args, FExecStatus& Status)
{
	if (Args.Num() < 1)
	{
		FString Msg = TEXT("No sensor id is available");
		UE_LOG(LogTemp, Warning, TEXT("%s"), *Msg);
		Status = FExecStatus::Error(Msg);
		return nullptr;
	}
	int SensorId = FCString::Atoi(*Args[0]);
	UFusionCamSensor* FusionSensor = USensorBPLib::GetSensorById(SensorId);
	if (!IsValid(FusionSensor))
	{
		FString Msg = TEXT("Invalid sensor id");
		UE_LOG(LogTemp, Warning, TEXT("%s"), *Msg);
		Status = FExecStatus::Error(Msg);
		return nullptr;
	}
	return FusionSensor;
}

TArray<UFusionCamSensor*> FLychSimCameraHandler::GetCameraBatch(const TArray<FString>& Args, FExecStatus& Status)
{
	if (Args.Num() < 1)
	{
		FString Msg = TEXT("No sensor id is available");
		UE_LOG(LogTemp, Warning, TEXT("%s"), *Msg);
		Status = FExecStatus::Error(Msg);
		return TArray<UFusionCamSensor*>();
	}

	TArray<UFusionCamSensor*> Sensors;

	for (int32 i = 0; i < Args.Num() - 1; ++i)
	{
		const FString& Arg = Args[i];
		int SensorId = FCString::Atoi(*Arg);
		UFusionCamSensor* FusionSensor = USensorBPLib::GetSensorById(SensorId);

		if (!IsValid(FusionSensor))
		{
			UE_LOG(LogLychSim, Warning, TEXT("Invalid sensor id: %d"), SensorId);
			return TArray<UFusionCamSensor*>();
		}

		Sensors.Add(FusionSensor);
	}

	return Sensors;
}

FExecStatus FLychSimCameraHandler::GetCameraLocation(const TArray<FString>& Args)
{
	FLychSimStructuredResponse R;
	FExecStatus Status = FExecStatus::OK();
	UFusionCamSensor* FusionCamSensor = GetCamera(Args, Status);
	if (!IsValid(FusionCamSensor)) return R.Error(Status.MessageBody);

	const int32 CamId = FCString::Atoi(*Args[0]);
	FVector Location = FusionCamSensor->GetSensorLocation();

	R.BeginOutputs();
	R.Writer()->WriteObjectStart();
	R.Writer()->WriteValue(TEXT("cam_id"), CamId);
	R.Writer()->WriteValue(TEXT("status"), TEXT("ok"));
	R.Writer()->WriteArrayStart(TEXT("location"));
	R.Writer()->WriteValue(Location.X); R.Writer()->WriteValue(Location.Y); R.Writer()->WriteValue(Location.Z);
	R.Writer()->WriteArrayEnd();
	R.Writer()->WriteObjectEnd();
	return R.FinishBatch(1, 1, FString());
}

FExecStatus FLychSimCameraHandler::GetCameraRotation(const TArray<FString>& Args)
{
	FLychSimStructuredResponse R;
	FExecStatus Status = FExecStatus::OK();
	UFusionCamSensor* FusionCamSensor = GetCamera(Args, Status);
	if (!IsValid(FusionCamSensor)) return R.Error(Status.MessageBody);

	const int32 CamId = FCString::Atoi(*Args[0]);
	FRotator Rotation = FusionCamSensor->GetSensorRotation();

	R.BeginOutputs();
	R.Writer()->WriteObjectStart();
	R.Writer()->WriteValue(TEXT("cam_id"), CamId);
	R.Writer()->WriteValue(TEXT("status"), TEXT("ok"));
	R.Writer()->WriteArrayStart(TEXT("rotation"));
	R.Writer()->WriteValue(Rotation.Pitch); R.Writer()->WriteValue(Rotation.Yaw); R.Writer()->WriteValue(Rotation.Roll);
	R.Writer()->WriteArrayEnd();
	R.Writer()->WriteObjectEnd();
	return R.FinishBatch(1, 1, FString());
}

FExecStatus FLychSimCameraHandler::GetCameraFOV(const TArray<FString>& Args)
{
	FLychSimStructuredResponse R;
	FExecStatus Status = FExecStatus::OK();
	UFusionCamSensor* FusionCamSensor = GetCamera(Args, Status);
	if (!IsValid(FusionCamSensor)) return R.Error(Status.MessageBody);

	const int32 CamId = FCString::Atoi(*Args[0]);
	float FOV = FusionCamSensor->GetSensorFOV();

	R.BeginOutputs();
	R.Writer()->WriteObjectStart();
	R.Writer()->WriteValue(TEXT("cam_id"), CamId);
	R.Writer()->WriteValue(TEXT("status"), TEXT("ok"));
	R.Writer()->WriteValue(TEXT("fov"), FOV);
	R.Writer()->WriteObjectEnd();
	return R.FinishBatch(1, 1, FString());
}

FExecStatus FLychSimCameraHandler::GetCameraC2W(const TArray<FString>& Args)
{
	FLychSimStructuredResponse R;
	FExecStatus Status = FExecStatus::OK();
	UFusionCamSensor* FusionCamSensor = GetCamera(Args, Status);
	if (!IsValid(FusionCamSensor)) return R.Error(Status.MessageBody);

	const int32 CamId = FCString::Atoi(*Args[0]);
	FTransform CameraTransform = FusionCamSensor->GetComponentTransform();
	FMatrix C2W = CameraTransform.ToMatrixWithScale();

	R.BeginOutputs();
	R.Writer()->WriteObjectStart();
	R.Writer()->WriteValue(TEXT("cam_id"), CamId);
	R.Writer()->WriteValue(TEXT("status"), TEXT("ok"));
	R.Writer()->WriteArrayStart(TEXT("c2w"));
	for (int32 Row = 0; Row < 4; ++Row)
	{
		R.Writer()->WriteArrayStart();
		for (int32 Col = 0; Col < 4; ++Col)
		{
			R.Writer()->WriteValue(C2W.M[Row][Col]);
		}
		R.Writer()->WriteArrayEnd();
	}
	R.Writer()->WriteArrayEnd();
	R.Writer()->WriteObjectEnd();
	return R.FinishBatch(1, 1, FString());
}

FExecStatus FLychSimCameraHandler::SetFilmSize(const TArray<FString>& Args)
{
	FLychSimStructuredResponse R;
	FExecStatus Status = FExecStatus::OK();
	UFusionCamSensor* FusionCamSensor = GetCamera(Args, Status);
	if (!IsValid(FusionCamSensor)) return R.Error(Status.MessageBody);

	if (Args.Num() != 3) return R.Error(TEXT("expected: <cam_id> <width> <height>"));

	int Width = FCString::Atoi(*Args[1]);
	int Height = FCString::Atoi(*Args[2]);
	FusionCamSensor->SetFilmSize(Width, Height);
	return R.Ok();
}

FExecStatus FLychSimCameraHandler::GetCameraLit(
	const TArray<FString>& Pos,
    const TMap<FString,FString>& Kw,
    const TSet<FString>& Flags)
{
	// In non-batch mode, Pos only contains one sensor id and save path. With more than two elements,
	// it will be regarded as batch mode with multiple sensor ids.
	if (Pos.Num() > 2)
	{
		return GetCameraLitBatch(Pos, Kw, Flags);
	}

	FExecStatus ExecStatus = FExecStatus::OK();
	UFusionCamSensor* FusionCamSensor = GetCamera(Pos, ExecStatus);
	if (!IsValid(FusionCamSensor)) return EnvelopeError(ExecStatus.MessageBody);

	int WarmupFrames = 0;
	if (Kw.Contains("warmup"))
	{
		WarmupFrames = FCString::Atoi(*Kw["warmup"]);
	}

	TArray<FColor> Data;
	int Width = 0, Height = 0;
	bool bExperimental = Flags.Contains("experimental");
	FusionCamSensor->GetLit(Data, Width, Height, WarmupFrames, ELitMode::Lit, bExperimental);
	LychSim::SaveData(Data, Width, Height, Pos, ExecStatus);
	if (ExecStatus != FExecStatusType::OK) return EnvelopeError(ExecStatus.MessageBody);
	return ExecStatus;
}

static bool CaptureLitBatch_EnqueueReadbacks(
	const TArray<ULitCamSensor*>& Sensors,
	int32 WarmupFrames,
	TArray<FLitReadbackRequest>& OutRequests,
	int32& OutWidth,
	int32& OutHeight)
{
	OutRequests.Reset();
    OutWidth = 0;
    OutHeight = 0;

	if (Sensors.Num() == 0) return false;

	for (ULitCamSensor* S : Sensors)
	{
		if (!S->EnsureTextureTarget())
		{
			OutRequests.Reset();
			return false;
		}
	}

	OutWidth  = Sensors[0]->GetFilmWidth();
	OutHeight = Sensors[0]->GetFilmHeight();

	for (int32 f = 0; f < WarmupFrames; ++f)
	{
		for (ULitCamSensor* S : Sensors)
		{
			S->CaptureScene();
		}
		FlushRenderingCommands();
	}

	for (ULitCamSensor* S : Sensors)
	{
		S->CaptureScene();
	}

	OutRequests.SetNum(Sensors.Num());
	for (int32 i = 0; i < Sensors.Num(); ++i)
	{
		ULitCamSensor* S = Sensors[i];
		UTextureRenderTarget2D* RT = S->TextureTarget;

		FLitReadbackRequest& Req = OutRequests[i];
		Req.Sensor = S;
		Req.Width  = RT->SizeX;
        Req.Height = RT->SizeY;
        Req.Readback = MakeUnique<FRHIGPUTextureReadback>(TEXT("LitReadback"));
        Req.bEnqueued = true;

		FTextureRenderTargetResource* RTRes = RT->GameThread_GetRenderTargetResource();
		FRHIGPUTextureReadback* ReadbackPtr = Req.Readback.Get();

		ENQUEUE_RENDER_COMMAND(EnqueueLitReadback)(
            [RTRes, ReadbackPtr](FRHICommandListImmediate& RHICmdList)
            {
                FRHITexture* SrcTexture = RTRes->GetRenderTargetTexture();
                ReadbackPtr->EnqueueCopy(RHICmdList, SrcTexture);
            }
        );
	}

	return true;
}

static bool CaptureLitBatch_TryResolve(
    TArray<FLitReadbackRequest>& InOutRequests,
    TArray<TArray<FColor>>& OutImages)
{
	const int32 N = InOutRequests.Num();
	if (N == 0) return false;

	for (FLitReadbackRequest& Req : InOutRequests)
	{
		if (!Req.bEnqueued || !Req.Readback.IsValid())
		{
			UE_LOG(LogLychSim, Warning, TEXT("Req.bEnqueued: %d, Req.Readback.IsValid: %d"), Req.bEnqueued, Req.Readback.IsValid());
			return false;
		}
		if (!Req.Readback->IsReady())
		{
			UE_LOG(LogLychSim, Warning, TEXT("Req.Readback->IsReady() is false"));
			return false;
		}
	}

	OutImages.SetNum(N);
	for (int32 i = 0; i < N; ++i)
	{
		FLitReadbackRequest& Req = InOutRequests[i];
		const int32 Width  = Req.Width;
        const int32 Height = Req.Height;

		TArray<FColor>& Img = OutImages[i];
		Img.SetNumUninitialized(Width * Height);

		const int32 BytesPerPixel = 4;
		const int32 TotalBytes = Width * Height * BytesPerPixel;

		int32 RowPitchInPixels = 0;
		int BufferHeight = 0;

		void* SrcPtr = Req.Readback->Lock(RowPitchInPixels, &BufferHeight);

		const int32 AssumedBpp = 4;
		const int64 TotalBytesFromReadback = int64(RowPitchInPixels) * int64(BufferHeight) * int64(AssumedBpp);

		const int32 RowPitchInBytes = RowPitchInPixels * BytesPerPixel;

		uint8* Src = static_cast<uint8*>(SrcPtr);
		uint8* Dst = reinterpret_cast<uint8*>(Img.GetData());

		int32 EffectiveHeight = FMath::Min(Height, BufferHeight);
		if (EffectiveHeight != Height)
		{
			UE_LOG(LogLychSim, Warning, TEXT("Height mismatch! Expected: %d, BufferHeight: %d, will only copy %d rows"), Height, BufferHeight, EffectiveHeight);
		}

		if (RowPitchInBytes == Width * BytesPerPixel)
		{
			FMemory::Memcpy(Dst, Src, EffectiveHeight * Width * BytesPerPixel);
		}
		else
		{
			for (int32 y = 0; y < EffectiveHeight; ++y)
			{
				FMemory::Memcpy(
					Dst + y * Width * BytesPerPixel,
					Src + y * RowPitchInBytes,
					Width * BytesPerPixel
				);
			}
		}

		Req.Readback->Unlock();
		Req.bEnqueued = false;
		Req.Readback.Reset();
	}

	InOutRequests.Reset();

	return true;
}

FExecStatus FLychSimCameraHandler::GetCameraLitBatch(
	const TArray<FString>& Pos,
    const TMap<FString,FString>& Kw,
    const TSet<FString>& Flags)
{
	// Need at least one sensor id + the save-path token.
	if (Pos.Num() < 2)
	{
		return EnvelopeError(TEXT("expected: <cam_id>... npy"));
	}

	// ensure that the save path is npy
	if (Pos.Last() != TEXT("npy"))
	{
		return EnvelopeError(TEXT("save path must be 'npy' in batch mode"));
	}

	FExecStatus ExecStatus = FExecStatus::OK();

	TArray<UFusionCamSensor*> Sensors = GetCameraBatch(Pos, ExecStatus);
	if (Sensors.Num() < 1) {
		return EnvelopeError(TEXT("invalid sensor id in batch request"));
	}

	// cast all to lit sensors
	TArray<ULitCamSensor*> LitSensors;
	LitSensors.Reserve(Sensors.Num());
	for (UFusionCamSensor* S : Sensors)
	{
		ULitCamSensor* Lit = S->GetLitCamSensor();
		if (!IsValid(Lit))
		{
			return EnvelopeError(TEXT("sensor is not a lit camera sensor"));
		}
		LitSensors.Add(Lit);
	}

	int WarmupFrames = 0;
	if (Kw.Contains("warmup"))
	{
		WarmupFrames = FCString::Atoi(*Kw["warmup"]);
	}

	// batch capture + enqueue
	int32 Width = 0, Height = 0;
	TArray<FLitReadbackRequest> Requests;
	const bool bEnqueued = CaptureLitBatch_EnqueueReadbacks(
		LitSensors,
		WarmupFrames,
		Requests,
		Width,
		Height);

	UE_LOG(LogLychSim, Log, TEXT("bEnqueued: %d"), bEnqueued);
	UE_LOG(LogLychSim, Log, TEXT("Number of requests: %d"), Requests.Num());

	if (!bEnqueued || Requests.Num() != LitSensors.Num())
	{
		return EnvelopeError(TEXT("failed to enqueue GPU readbacks for batch lit capture"));
	}

	// try resolve readback
	TArray<TArray<FColor>> Images;
	bool bResolved = false;

	const int32 MaxPollIters = 100;
	for (int32 Iter = 0; Iter < MaxPollIters; ++Iter)
	{
		if (CaptureLitBatch_TryResolve(Requests, Images))
		{
			bResolved = true;
			break;
		}
		FlushRenderingCommands();
		FPlatformProcess::Sleep(0.01f);
	}

	if (!bResolved || Images.Num() != Sensors.Num())
	{
		return EnvelopeError(TEXT("timed out waiting for GPU readback in batch lit capture"));
	}

	auto SRGBToLinear = [](uint8 v)->float {
		float s = v / 255.0f;
		return (s <= 0.04045f) ? (s / 12.92f) : FMath::Pow((s + 0.055f) / 1.055f, 2.4f);
	};

	auto LinearToByte = [](float x)->uint8 {
		x = FMath::Clamp(x, 0.0f, 1.0f);
		return (uint8)FMath::RoundToInt(x * 255.0f);
	};

	// Correspond to ReadSurfaceDataFlags.SetLinearToGamma(false);
	for (TArray<FColor>& Img : Images)
	{
		for (FColor& P : Img)
		{
			float r = SRGBToLinear(P.R);
			float g = SRGBToLinear(P.G);
			float b = SRGBToLinear(P.B);

			P.R = LinearToByte(r);
			P.G = LinearToByte(g);
			P.B = LinearToByte(b);
			P.A = 255;
		}
	}

	LychSim::SaveData4D(Images, Images.Num(), Width, Height, Pos, ExecStatus);
	if (ExecStatus != FExecStatusType::OK) return EnvelopeError(ExecStatus.MessageBody);
	return ExecStatus;
}

FExecStatus FLychSimCameraHandler::WarmupCamera(const TArray<FString>& Args)
{
	FLychSimStructuredResponse R;
	FExecStatus Status = FExecStatus::OK();
	UFusionCamSensor* FusionCamSensor = GetCamera(Args, Status);
	if (!IsValid(FusionCamSensor)) return R.Error(Status.MessageBody);

	TArray<FColor> Data;
	int Width = 0;
	int Height = 0;
	int WarmupFrames = 0; // ensure deterministic warmup length
	FusionCamSensor->GetLit(Data, Width, Height, WarmupFrames);
	return R.Ok();
}

FExecStatus FLychSimCameraHandler::GetCameraSeg(const TArray<FString>& Args)
{
	FExecStatus ExecStatus = FExecStatus::OK();
	UFusionCamSensor* FusionCamSensor = GetCamera(Args, ExecStatus);
	if (!IsValid(FusionCamSensor)) return EnvelopeError(ExecStatus.MessageBody);

	TWeakObjectPtr<AUnrealcvWorldController> WorldController = FUnrealcvServer::Get().WorldController;
	if (WorldController.IsValid())
	{
		WorldController->EnsureAnnotations();
	}

	TArray<FColor> Data;
	int Width = 0, Height = 0;
	FusionCamSensor->GetSeg(Data, Width, Height);

	LychSim::SaveData(Data, Width, Height, Args, ExecStatus);
	if (ExecStatus != FExecStatusType::OK) return EnvelopeError(ExecStatus.MessageBody);
	return ExecStatus;
}

FExecStatus FLychSimCameraHandler::GetCameraElementSeg(const TArray<FString>& Args)
{
	FExecStatus ExecStatus = FExecStatus::OK();
	UFusionCamSensor* FusionCamSensor = GetCamera(Args, ExecStatus);
	if (!IsValid(FusionCamSensor)) return EnvelopeError(ExecStatus.MessageBody);

	TWeakObjectPtr<AUnrealcvWorldController> WorldController = FUnrealcvServer::Get().WorldController;
	FString OriginalMode;
	bool bRestoreAnnotations = false;

	if (WorldController.IsValid())
	{
		AUnrealcvWorldController* Controller = WorldController.Get();
		OriginalMode = Controller->GetSegmentationMode();

		UWorld* World = FUnrealcvServer::Get().GetWorld();
		if (IsValid(World))
		{
			Controller->ClearAnnotations();
			Controller->ObjectAnnotator.AnnotateWorldByElement(World);
			bRestoreAnnotations = true;
		}
		else
		{
			UE_LOG(LogLychSim, Warning, TEXT("World is not valid when building element segmentation"));
			Controller->EnsureAnnotations();
		}
	}
	else
	{
		UE_LOG(LogLychSim, Warning, TEXT("WorldController is not valid for element segmentation; falling back to object segmentation"));
	}

	TArray<FColor> Data;
	int Width = 0, Height = 0;
	FusionCamSensor->GetSeg(Data, Width, Height);

	LychSim::SaveData(Data, Width, Height, Args, ExecStatus);

	if (bRestoreAnnotations && WorldController.IsValid())
	{
		AUnrealcvWorldController* Controller = WorldController.Get();
		Controller->SetSegmentationMode(OriginalMode);
		Controller->RebuildAnnotations();
	}
	else if (WorldController.IsValid())
	{
		WorldController->EnsureAnnotations();
	}

	if (ExecStatus != FExecStatusType::OK) return EnvelopeError(ExecStatus.MessageBody);
	return ExecStatus;
}

FExecStatus FLychSimCameraHandler::AnnotateNewObjects(const TArray<FString>& Args)
{
	FLychSimStructuredResponse R;
	TWeakObjectPtr<AUnrealcvWorldController> WorldController = FUnrealcvServer::Get().WorldController;
	if (!WorldController.IsValid())
	{
		return R.Error(TEXT("WorldController is not valid"));
	}
	WorldController->AnnotateNewObjects();
	return R.Ok();
}

FExecStatus FLychSimCameraHandler::ClearAnnotationComponents(const TArray<FString>& Args)
{
	FLychSimStructuredResponse R;
	TWeakObjectPtr<AUnrealcvWorldController> WorldController = FUnrealcvServer::Get().WorldController;
	if (!WorldController.IsValid())
	{
		return R.Error(TEXT("WorldController is not valid"));
	}
	WorldController->ClearAnnotations();
	return R.Ok();
}

FExecStatus FLychSimCameraHandler::GetPointMap(
	const TArray<FString>& Pos,
	const TMap<FString,FString>& Kw,
	const TSet<FString>& Flags)
{
	FExecStatus ExecStatus = FExecStatus::OK();
	UFusionCamSensor* FusionCamSensor = GetCamera(Pos, ExecStatus);
	if (!IsValid(FusionCamSensor)) return EnvelopeError(ExecStatus.MessageBody);

	const FString Filename = Pos.Num() >= 2 ? Pos[1] : TEXT("npy");

	FString Space = TEXT("all");
	if (Kw.Contains(TEXT("space")))
	{
		Space = Kw[TEXT("space")];
	}
	Space.ToLowerInline();

	const bool bCameraSpace = Space == TEXT("camera") || Space == TEXT("all") || Flags.Contains(TEXT("camera"));
	const bool bWorldSpace = Space == TEXT("world") || Space == TEXT("all") || Flags.Contains(TEXT("world"));
	const bool bOpenCVSpace = Space == TEXT("opencv") || Space == TEXT("all") || Flags.Contains(TEXT("opencv"));

	if (!bCameraSpace && !bWorldSpace && !bOpenCVSpace)
	{
		return EnvelopeError(TEXT("Invalid space; expected camera, world, opencv or all."));
	}

	TArray<FVector> CameraPoints;
	TArray<FVector> WorldPoints;
	TArray<FVector> OpenCVPoints;
	int Width = 0;
	int Height = 0;
	FusionCamSensor->GetPointMaps(CameraPoints, WorldPoints, OpenCVPoints, Width, Height, bCameraSpace, bWorldSpace, bOpenCVSpace);

	if (Width <= 0 || Height <= 0)
	{
		return EnvelopeError(TEXT("Invalid film size when building point map."));
	}

	const int32 Channels =
		(bCameraSpace ? 3 : 0) +
		(bWorldSpace ? 3 : 0) +
		(bOpenCVSpace ? 3 : 0);

	if (Channels == 0)
	{
		return EnvelopeError(TEXT("No point map channels requested."));
	}

	const int64 NumPixels = static_cast<int64>(Width) * static_cast<int64>(Height);
	TArray<float> Data;
	Data.SetNumZeroed(NumPixels * Channels);

	for (int64 Index = 0; Index < NumPixels; ++Index)
	{
		int32 ChannelOffset = 0;
		const int64 Base = Index * Channels;

		if (bCameraSpace && CameraPoints.IsValidIndex(Index))
		{
			const FVector& P = CameraPoints[Index];
			Data[Base + ChannelOffset + 0] = P.X; // forward
			Data[Base + ChannelOffset + 1] = P.Y; // right
			Data[Base + ChannelOffset + 2] = P.Z; // up
			ChannelOffset += 3;
		}

		if (bWorldSpace && WorldPoints.IsValidIndex(Index))
		{
			const FVector& P = WorldPoints[Index];
			Data[Base + ChannelOffset + 0] = P.X;
			Data[Base + ChannelOffset + 1] = P.Y;
			Data[Base + ChannelOffset + 2] = P.Z;
			ChannelOffset += 3;
		}

		if (bOpenCVSpace && OpenCVPoints.IsValidIndex(Index))
		{
			const FVector& P = OpenCVPoints[Index]; // right, down, forward
			Data[Base + ChannelOffset + 0] = P.X;
			Data[Base + ChannelOffset + 1] = P.Y;
			Data[Base + ChannelOffset + 2] = P.Z;
		}
	}

	FExecStatus SerStatus = LychSim::SerializeData(Data, Width, Height, Filename, /*ChannelFirst=*/false);
	if (SerStatus != FExecStatusType::OK) return EnvelopeError(SerStatus.MessageBody);
	return SerStatus;
}

FExecStatus FLychSimCameraHandler::GetCameraDepth(const TArray<FString>& Args)
{
	FExecStatus ExecStatus = FExecStatus::OK();
	UFusionCamSensor* FusionCamSensor = GetCamera(Args, ExecStatus);
	if (!IsValid(FusionCamSensor)) return EnvelopeError(ExecStatus.MessageBody);

	TArray<float> Data;
	int Width = 0, Height = 0;
	FusionCamSensor->GetDepth(Data, Width, Height);

	LychSim::SaveData(Data, Width, Height, Args, ExecStatus);
	if (ExecStatus != FExecStatusType::OK) return EnvelopeError(ExecStatus.MessageBody);
	return ExecStatus;
}

FExecStatus FLychSimCameraHandler::GetCameraNormal(const TArray<FString>& Args)
{
	FExecStatus ExecStatus = FExecStatus::OK();
	UFusionCamSensor* FusionCamSensor = GetCamera(Args, ExecStatus);
	if (!IsValid(FusionCamSensor)) return EnvelopeError(ExecStatus.MessageBody);

	TArray<FColor> Data;
	int Width = 0, Height = 0;
	FusionCamSensor->GetNormal(Data, Width, Height);
	LychSim::SaveData(Data, Width, Height, Args, ExecStatus);
	if (ExecStatus != FExecStatusType::OK) return EnvelopeError(ExecStatus.MessageBody);
	return ExecStatus;
}

FExecStatus FLychSimCameraHandler::SetCameraLocation(const TArray<FString>& Args)
{
	FLychSimStructuredResponse R;
	FExecStatus Status = FExecStatus::OK();
	UFusionCamSensor* FusionCamSensor = GetCamera(Args, Status);
	if (!IsValid(FusionCamSensor)) return R.Error(Status.MessageBody);

	if (Args.Num() != 4) return R.Error(TEXT("expected: <cam_id> <x> <y> <z>"));

	float X = FCString::Atof(*Args[1]), Y = FCString::Atof(*Args[2]), Z = FCString::Atof(*Args[3]);
	FusionCamSensor->SetSensorLocation(FVector(X, Y, Z));
	return R.Ok();
}

FExecStatus FLychSimCameraHandler::SetCameraRotation(const TArray<FString>& Args)
{
	FLychSimStructuredResponse R;
	FExecStatus Status = FExecStatus::OK();
	UFusionCamSensor* FusionCamSensor = GetCamera(Args, Status);
	if (!IsValid(FusionCamSensor)) return R.Error(Status.MessageBody);

	if (Args.Num() != 4) return R.Error(TEXT("expected: <cam_id> <pitch> <yaw> <roll>"));

	float Pitch = FCString::Atof(*Args[1]), Yaw = FCString::Atof(*Args[2]), Roll = FCString::Atof(*Args[3]);
	FusionCamSensor->SetSensorRotation(FRotator(Pitch, Yaw, Roll));
	return R.Ok();
}

FExecStatus FLychSimCameraHandler::SetCameraFOV(const TArray<FString>& Args)
{
	FLychSimStructuredResponse R;
	FExecStatus Status = FExecStatus::OK();
	UFusionCamSensor* FusionCamSensor = GetCamera(Args, Status);
	if (!IsValid(FusionCamSensor)) return R.Error(Status.MessageBody);

	if (Args.Num() != 2) return R.Error(TEXT("expected: <cam_id> <fov>"));

	float FOV = FCString::Atof(*Args[1]);
	FusionCamSensor->SetSensorFOV(FOV);
	return R.Ok();
}

FExecStatus FLychSimCameraHandler::IsPoseInvalid(const TArray<FString>& Args)
{
	FLychSimStructuredResponse R;
	FExecStatus Status = FExecStatus::OK();
	UFusionCamSensor* FusionCamSensor = GetCamera(Args, Status);
	if (!IsValid(FusionCamSensor)) return R.Error(Status.MessageBody);

	if (Args.Num() != 4 && Args.Num() != 5)
	{
		return R.Error(TEXT("expected: <cam_id> <x> <y> <z> [radius_cm]"));
	}

	const int32 CamId = FCString::Atoi(*Args[0]);
	const float X = FCString::Atof(*Args[1]);
	const float Y = FCString::Atof(*Args[2]);
	const float Z = FCString::Atof(*Args[3]);
	const FVector TestLocation(X, Y, Z);

	const float SafetyRadiusCm = Args.Num() == 5 ? FCString::Atof(*Args[4]) : 5.0f;
	if (SafetyRadiusCm <= 0.0f)
	{
		return R.Error(TEXT("Safety radius must be > 0 (cm)."));
	}

	UWorld* World = FusionCamSensor->GetWorld();
	if (!IsValid(World))
	{
		return R.Error(TEXT("World is invalid."));
	}

	FCollisionQueryParams QueryParams(SCENE_QUERY_STAT(LychCamPoseOverlap), /*bTraceComplex=*/true);
	QueryParams.bFindInitialOverlaps = true;
	if (AActor* OwnerActor = FusionCamSensor->GetOwner())
	{
		QueryParams.AddIgnoredActor(OwnerActor);
	}

	FCollisionObjectQueryParams ObjectQueryParams;
	ObjectQueryParams.AddObjectTypesToQuery(ECC_WorldStatic);
	ObjectQueryParams.AddObjectTypesToQuery(ECC_WorldDynamic);
	ObjectQueryParams.AddObjectTypesToQuery(ECC_Pawn);

	const FCollisionShape QuerySphere = FCollisionShape::MakeSphere(SafetyRadiusCm);
	const bool bInvalid = World->OverlapAnyTestByObjectType(
		TestLocation,
		FQuat::Identity,
		ObjectQueryParams,
		QuerySphere,
		QueryParams
	);

	R.BeginOutputs();
	R.Writer()->WriteObjectStart();
	R.Writer()->WriteValue(TEXT("cam_id"), CamId);
	R.Writer()->WriteValue(TEXT("status"), TEXT("ok"));
	R.Writer()->WriteValue(TEXT("invalid"), bInvalid);
	R.Writer()->WriteObjectEnd();
	return R.FinishBatch(1, 1, FString());
}

FExecStatus FLychSimCameraHandler::GetCameraAnnotations(const TArray<FString>& Args)
{
	FLychSimStructuredResponse R;
	FExecStatus Status = FExecStatus::OK();
	UFusionCamSensor* FusionCamSensor = GetCamera(Args, Status);
	if (!IsValid(FusionCamSensor)) return R.Error(Status.MessageBody);

	const int32 CamId = FCString::Atoi(*Args[0]);
	const FVector Location = FusionCamSensor->GetSensorLocation();
	const FRotator Rotation = FusionCamSensor->GetSensorRotation();
	const float FOV = FusionCamSensor->GetSensorFOV();
	const FMatrix C2W = FusionCamSensor->GetComponentTransform().ToMatrixWithScale();
	const int32 Width = FusionCamSensor->GetFilmWidth();
	const int32 Height = FusionCamSensor->GetFilmHeight();

	R.BeginOutputs();
	R.Writer()->WriteObjectStart();
	R.Writer()->WriteValue(TEXT("cam_id"), CamId);
	R.Writer()->WriteValue(TEXT("status"), TEXT("ok"));

	R.Writer()->WriteArrayStart(TEXT("location"));
	R.Writer()->WriteValue(Location.X); R.Writer()->WriteValue(Location.Y); R.Writer()->WriteValue(Location.Z);
	R.Writer()->WriteArrayEnd();

	R.Writer()->WriteArrayStart(TEXT("rotation"));
	R.Writer()->WriteValue(Rotation.Pitch); R.Writer()->WriteValue(Rotation.Yaw); R.Writer()->WriteValue(Rotation.Roll);
	R.Writer()->WriteArrayEnd();

	R.Writer()->WriteValue(TEXT("fov"), FOV);

	R.Writer()->WriteArrayStart(TEXT("c2w"));
	for (int32 Row = 0; Row < 4; ++Row)
	{
		R.Writer()->WriteArrayStart();
		for (int32 Col = 0; Col < 4; ++Col)
		{
			R.Writer()->WriteValue(C2W.M[Row][Col]);
		}
		R.Writer()->WriteArrayEnd();
	}
	R.Writer()->WriteArrayEnd();

	R.Writer()->WriteValue(TEXT("width"), Width);
	R.Writer()->WriteValue(TEXT("height"), Height);

	R.Writer()->WriteObjectEnd();
	return R.FinishBatch(1, 1, FString());
}

FExecStatus FLychSimCameraHandler::GetZBuffer(
	const TArray<FString>& Pos,
    const TMap<FString,FString>& Kw,
    const TSet<FString>& Flags)
{
	TArray<AActor*> ActorList;
	if (Flags.Contains("all"))
	{
		UVisionBPLib::GetActorList(ActorList);
	}
	else
	{
		// first positional argument is camera id
		for (int32 i = 1; i < Pos.Num(); ++i)
		{
			const FString& ActorId = Pos[i];
			AActor* Actor = GetActorById(FUnrealcvServer::Get().GetWorld(), ActorId);
			if (!IsValid(Actor))
			{
				return EnvelopeError(FString::Printf(TEXT("Actor %s is not valid"), *ActorId));
			}
			ActorList.Add(Actor);
		}
	}

	FExecStatus ExecStatus = FExecStatus::OK();
	UFusionCamSensor* FusionCamSensor = GetCamera(Pos, ExecStatus);
	if (!IsValid(FusionCamSensor)) return EnvelopeError(ExecStatus.MessageBody);

	TArray<float> Data;
	int Width = 0, Height = 0;
	FusionCamSensor->GetZBuffer(Data, ActorList, Width, Height);

	LychSim::SaveDataNPY(Data, Width, Height, ExecStatus, /*ChannelFirst=*/true);
	if (ExecStatus != FExecStatusType::OK) return EnvelopeError(ExecStatus.MessageBody);
	return ExecStatus;
}
