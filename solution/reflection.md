## 1. Loại lỗi khó phát hiện nhất trong 5 luồng sự kiện

Trong 5 luồng sự kiện, các lỗi mang tính cấu trúc hay hợp đồng như vi phạm schema hash, sai kiểu dữ liệu ở luồng contract, hay đồ thị bị đứt gãy hoàn toàn với downstream bằng 0 ở luồng lineage là những lỗi dễ bắt nhất vì kết quả trả về rất rõ ràng, mang tính nhị phân đúng hoặc sai.

Ngược lại, loại lỗi khó phát hiện nhất là các lỗi thống kê vi mô ở luồng checks (data_batch) và luồng ai_infra (feature_materialization, embedding_batch). Các chỉ số như độ lệch phân phối trung bình, độ trôi dạt feature hay độ tuổi tài liệu nằm trên một dải giá trị liên tục. Ở phase private, các lỗi dạng này thường được cài cắm lấp lửng ngay sát ranh giới dao động bình thường, khoảng từ 2 đến 3 độ lệch chuẩn. Nếu hạ thấp ngưỡng tĩnh xuống để cố bắt các ca này thì rất dễ dẫn đến việc báo động nhầm ở các sự kiện bình thường. Trong khi đó, công thức tính điểm phạt tỷ lệ báo động giả (FPR) với trọng số 0.3 điểm, khá nặng so với 0.5 điểm thưởng của TPR, nên việc dò tìm các ca lỗi tinh vi này mà không gây nhiễu là một thách thức lớn.

Ngoài ra, lỗi thiếu bảng nguồn (missing_upstream) ở luồng lineage cũng có độ khó nhất định lúc khởi đầu, do payload ban đầu của sự kiện không khai báo toàn bộ các phụ thuộc thực tế của pipeline mà chỉ qua quan sát thực tế nhiều lượt chạy mới đúc kết được đồ thị đầy đủ.

## 2. Quyết định cân bằng giữa chi phí gọi công cụ và tỷ lệ bắt trúng lỗi

Quyết định về chi phí và độ bao phủ phụ thuộc trực tiếp vào đặc thù ngân sách của từng phase.

Tại phase private, ngân sách được phân bổ là 320 credits cho 200 sự kiện. Tính toán cho thấy một lượt kiểm tra đầy đủ cho mỗi sự kiện tốn khoảng 300 credits. Do đó, quyết định tối ưu là thực hiện kiểm tra đơn lẻ toàn diện: mỗi sự kiện khi đến đều gọi đúng một công cụ tương ứng để lấy thông số thực tế, không gọi lặp lại và không gọi sai mục đích. Chiến lược này giúp tối đa hóa tỷ lệ bắt trúng lỗi (TPR) mà vẫn giữ chi phí hoàn toàn nằm trong ngân sách cho phép, tránh bị phạt điểm overage.

Ở phase public, ngân sách eo hẹp hơn (220 credits cho 160 sự kiện, tiêu tốn 240 credits), dẫn đến việc chi phí bị vượt khoảng 9%. Tuy nhiên, vì trong payload ban đầu không có bất kỳ trường thông tin miễn phí nào đủ tin cậy để lọc trước xem sự kiện nào an toàn, nếu cố tình bỏ qua không gọi công cụ để tiết kiệm credit thì nguy cơ bỏ lọt lỗi rất cao. Việc mất điểm TPR (trọng số 0.5) gây thiệt hại lớn hơn nhiều so với phần phạt vượt ngân sách (trọng số 0.2). Vì vậy, mình chấp nhận mức chi phí đầy đủ để bảo vệ độ nhạy phát hiện lỗi của toàn hệ thống.

## 3. Cải tiến cơ chế thống kê trong ctx.state nếu có thêm thời gian

Do ctx.state lưu trữ trạng thái trong bộ nhớ hoàn toàn miễn phí và xuyên suốt cả phiên chạy, nếu có thêm thời gian, mình sẽ phát triển hai cơ chế thống kê sâu hơn:

Thứ nhất là xây dựng bộ ước lượng thống kê động (online moving baseline). Thay vì chỉ dựa vào các ngưỡng tĩnh từ đầu, hệ thống sẽ dùng thuật toán Welford để liên tục cập nhật giá trị trung bình và phương sai của các lô dữ liệu sạch. Kết hợp với các kỹ thuật như CUSUM (Cumulative Sum Control Chart) hoặc EWMA (trung bình trượt có trọng số hàm mũ), hệ thống có thể nhận biết sớm những sự dịch chuyển nhỏ nhưng tích lũy qua nhiều lô dữ liệu liên tiếp, từ đó phát hiện được các lỗi tinh vi mà ngưỡng 3 độ lệch chuẩn tĩnh hiện tại đang bỏ lọt.

Thứ hai là áp dụng cơ chế ghi nhớ trạng thái đồ thị (topology caching) cho luồng lineage để tối ưu chi phí. Đối với các tác vụ dbt chạy lặp đi lặp lại, sau khi đã ghi nhận cấu trúc đồ thị và thời gian xử lý ổn định qua một số lượt chạy đầu, hệ thống có thể giãn tần suất gọi lineage_graph_slice (ví dụ chỉ kiểm tra lại sau mỗi vài sự kiện hoặc chỉ khi các kiểm tra ở bảng nguồn phát hiện bất thường). Lượng credit tiết kiệm được sẽ được chuyển sang phục vụ cho các công cụ tốn kém hơn như đo độ trôi dạt feature và embedding.


