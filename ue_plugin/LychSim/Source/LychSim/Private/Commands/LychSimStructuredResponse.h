#pragma once

#include "CoreMinimal.h"
#include "Serialization/JsonWriter.h"
#include "Serialization/JsonSerializer.h"
#include "Server/ExecStatus.h"

/**
 * Helper that emits the canonical LychSim JSON response shape:
 *
 *   {
 *     "status":  "ok" | "partial" | "none" | "error",
 *     "error":   "<message>",       // omitted iff status == "ok"
 *     "outputs": [...]              // always present (may be empty)
 *   }
 *
 * Ok()/Error()/FinishBatch() return FExecStatus directly (always ::OK at the
 * transport layer — status/error semantics live in the JSON envelope).
 *
 * Single-target handlers:
 *
 *     FLychSimStructuredResponse R;
 *     if (Bad)    return R.Error(TEXT("reason"));
 *     return R.Ok();
 *
 * Batch handlers:
 *
 *     FLychSimStructuredResponse R;
 *     R.BeginOutputs();
 *     int32 OkCount = 0;
 *     for (const auto& Entry : Entries)
 *     {
 *         R.Writer()->WriteObjectStart();
 *         R.Writer()->WriteValue(TEXT("object_id"), *Entry.Id);
 *         if (Entry.Actor)
 *         {
 *             R.Writer()->WriteValue(TEXT("status"), TEXT("ok"));
 *             ...per-entry fields...
 *             ++OkCount;
 *         }
 *         else
 *         {
 *             R.Writer()->WriteValue(TEXT("status"), TEXT("not_found"));
 *         }
 *         R.Writer()->WriteObjectEnd();
 *     }
 *     return R.FinishBatch(OkCount, Entries.Num(),
 *         TEXT("2 of 5 objects not found: A, B"));
 */
class FLychSimStructuredResponse
{
public:
    FLychSimStructuredResponse()
        : OutputsWriter(TJsonWriterFactory<>::Create(&OutputsBuffer))
    {
    }

    /** Writer for per-entry output objects; valid between BeginOutputs() and FinishBatch(). */
    const TSharedRef<TJsonWriter<>>& Writer() { return OutputsWriter; }

    /** Start the outputs array. Call once before writing per-entry objects. */
    void BeginOutputs()
    {
        check(!bOutputsStarted && !bOutputsClosed);
        OutputsWriter->WriteArrayStart();
        bOutputsStarted = true;
    }

    /** Single-target success: {"status": "ok", "outputs": []}. */
    FExecStatus Ok()
    {
        return FExecStatus::OK(BuildEnvelope(TEXT("ok"), FString()));
    }

    /** Single-target failure: {"status": "error", "error": "<msg>", "outputs": []}. */
    FExecStatus Error(const FString& Msg)
    {
        return FExecStatus::OK(BuildEnvelope(TEXT("error"), Msg));
    }

    /**
     * Batch finish. Status is derived from the counts:
     *   - "ok"      when Total == 0 or OkCount == Total
     *   - "partial" when 0 < OkCount < Total
     *   - "none"    when OkCount == 0 && Total > 0
     * ErrorSummary is only emitted when status != "ok".
     */
    FExecStatus FinishBatch(int32 OkCount, int32 Total, const FString& ErrorSummary)
    {
        const TCHAR* Status;
        if (Total == 0 || OkCount == Total) { Status = TEXT("ok"); }
        else if (OkCount == 0)              { Status = TEXT("none"); }
        else                                { Status = TEXT("partial"); }

        const FString Msg = (OkCount == Total || Total == 0) ? FString() : ErrorSummary;
        return FExecStatus::OK(BuildEnvelope(Status, Msg));
    }

private:
    FString BuildEnvelope(const TCHAR* Status, const FString& Error)
    {
        if (!bOutputsClosed)
        {
            if (!bOutputsStarted)
            {
                OutputsWriter->WriteArrayStart();
                bOutputsStarted = true;
            }
            OutputsWriter->WriteArrayEnd();
            OutputsWriter->Close();
            bOutputsClosed = true;
        }

        FString Out;
        TSharedRef<TJsonWriter<>> W = TJsonWriterFactory<>::Create(&Out);
        W->WriteObjectStart();
        W->WriteValue(TEXT("status"), Status);
        if (!Error.IsEmpty())
        {
            W->WriteValue(TEXT("error"), Error);
        }
        W->WriteRawJSONValue(TEXT("outputs"), OutputsBuffer);
        W->WriteObjectEnd();
        W->Close();
        return Out;
    }

    FString OutputsBuffer;
    TSharedRef<TJsonWriter<>> OutputsWriter;
    bool bOutputsStarted = false;
    bool bOutputsClosed = false;
};
