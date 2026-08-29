// speaker_box.swift — 프레임에서 ① 화자 위치 ② 이미 구워진 자막 띠 위치를 찾는다
//
// 맥 내장 Vision 프레임워크만 쓴다. 모델 다운로드도, 파이썬 패키지도 필요 없다.
// 컴파일 불필요:  swift speaker_box.swift frames/*.png > boxes.json
//
// ★ 프레임마다 찾지 않는다. 자막 큐 하나당 프레임 1장이면 된다.
//   강의 영상에서 화자는 자막 한 줄이 뜨는 2~3초 동안 화면을 가로지르지 않는다.
//   47컷이면 47장. 프레임 전수(24분=43,200장)를 돌리면 몇 시간이 걸린다.
//
// 좌표계 주의: Vision 은 [0,1] 정규화 + 원점이 '왼쪽 아래'다.
//   영상·ASS 는 원점이 '왼쪽 위'다. 여기서 변환해서 내보낸다(픽셀·좌상단 기준).

import Foundation
import Vision
import AppKit

struct Box: Codable {
    var x: Double, y: Double, w: Double, h: Double, conf: Double
    var text: String? = nil
}

struct FrameResult: Codable {
    var image: String
    var width: Int
    var height: Int
    var persons: [Box]
    var faces: [Box]
    var texts: [Box]
    var error: String? = nil
}

/// Vision 정규화 박스(좌하단 원점) → 픽셀 박스(좌상단 원점)
func toPixels(_ bb: CGRect, _ W: Int, _ H: Int, _ conf: Float) -> Box {
    let w = Double(bb.width) * Double(W)
    let h = Double(bb.height) * Double(H)
    let x = Double(bb.minX) * Double(W)
    let yBottom = Double(bb.minY) * Double(H)
    let y = Double(H) - yBottom - h          // 좌상단 기준으로 뒤집기
    return Box(x: (x*10).rounded()/10, y: (y*10).rounded()/10,
               w: (w*10).rounded()/10, h: (h*10).rounded()/10,
               conf: Double((conf*1000).rounded()/1000))
}

func analyze(_ path: String, wantText: Bool) -> FrameResult {
    guard let img = NSImage(contentsOfFile: path),
          let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
        return FrameResult(image: path, width: 0, height: 0,
                           persons: [], faces: [], texts: [], error: "이미지를 열 수 없음")
    }
    let W = cg.width, H = cg.height
    let handler = VNImageRequestHandler(cgImage: cg, options: [:])

    let human = VNDetectHumanRectanglesRequest()
    if #available(macOS 12.0, *) { human.upperBodyOnly = false }
    let face = VNDetectFaceRectanglesRequest()

    var reqs: [VNRequest] = [human, face]

    let text = VNRecognizeTextRequest()
    text.recognitionLevel = .accurate
    text.recognitionLanguages = ["ko-KR", "en-US"]
    text.usesLanguageCorrection = false
    if wantText {
        // ⛔ regionOfInterest 를 쓰지 않는다.
        //    ROI 를 주면 결과 boundingBox 가 '전체 화면'이 아니라 'ROI' 기준으로 돌아온다.
        //    실측: 아래 45% ROI 로 찾은 자막이 y=112(화면 위)로 나왔고,
        //    전체 스캔으로 같은 글자를 재니 y=642(화면 아래)였다. 검산 1080-486x0.8963=644.
        //    에러는 없었고 숫자도 그럴싸했다 — 전체 스캔과 대조해야만 잡힌다.
        //    항상 전체를 스캔하고, 자막 띠 판정(아래 몇 %)은 파이썬 쪽에서 y 로 거른다.
        reqs.append(text)
    }

    var persons: [Box] = [], faces: [Box] = [], texts: [Box] = []
    do {
        try handler.perform(reqs)
        for o in (human.results ?? []) { persons.append(toPixels(o.boundingBox, W, H, o.confidence)) }
        for o in (face.results  ?? []) { faces.append(toPixels(o.boundingBox, W, H, o.confidence)) }
        if wantText {
            for o in (text.results ?? []) {
                var b = toPixels(o.boundingBox, W, H, o.confidence)
                b.text = o.topCandidates(1).first?.string
                texts.append(b)
            }
        }
    } catch {
        return FrameResult(image: path, width: W, height: H,
                           persons: [], faces: [], texts: [], error: "\(error)")
    }
    persons.sort { $0.conf > $1.conf }
    faces.sort   { $0.conf > $1.conf }
    return FrameResult(image: path, width: W, height: H,
                       persons: persons, faces: faces, texts: texts)
}

// ── main ──────────────────────────────────────────────────────
var args = Array(CommandLine.arguments.dropFirst())
var wantText = true
args.removeAll { a in
    if a == "--no-text" { wantText = false; return true }
    return false
}
guard !args.isEmpty else {
    FileHandle.standardError.write("사용: swift speaker_box.swift [--no-text] frame1.png frame2.png ...\n".data(using: .utf8)!)
    exit(2)
}

let results = args.map { analyze($0, wantText: wantText) }
let enc = JSONEncoder()
enc.outputFormatting = [.prettyPrinted, .sortedKeys, .withoutEscapingSlashes]
FileHandle.standardOutput.write(try! enc.encode(results))
FileHandle.standardOutput.write("\n".data(using: .utf8)!)
